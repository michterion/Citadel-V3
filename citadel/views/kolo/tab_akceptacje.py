import streamlit as st
from config import teraz_utc
from database import db_query, db_execute, pool

def render_tab_akceptacje(curr_user_id):
    st.markdown("### 📥 Kolejka Weryfikacji Wpłat")
    st.caption("Wpłaty zadeklarowane przez Skarbników Kół i Regionów.")
    oczekujace_df = db_query("""
        SELECT wo.id, wo.kolo_id, k.nazwa as kolo_nazwa, wo.czlonek_id, c.imie_nazwisko as czlonek_nazwa,
               wo.kwota_gr, wo.data_wplaty, wo.notatka, wo.oswiadczenie, wo.data_zgloszenia,
               u.imie_nazwisko as zglosil_nazwa
        FROM wplaty_oczekujace wo
        JOIN kola k ON wo.kolo_id = k.id
        LEFT JOIN czlonkowie c ON wo.czlonek_id = c.id
        LEFT JOIN uzytkownicy u ON wo.zglosil_uzytkownik_id = u.id
        WHERE wo.status = 'OCZEKUJE'
        ORDER BY wo.data_zgloszenia ASC
    """)

    if oczekujace_df.empty:
        st.success("🎉 Brak oczekujących wpłat. Wszystkie transakcje są rozpatrzone!")
    else:
        for _, r_oczek in oczekujace_df.iterrows():
            o_id = r_oczek["id"]
            o_kolo = r_oczek["kolo_nazwa"]
            o_czl = r_oczek["czlonek_nazwa"] or "Brak przypisania"
            o_kwota = r_oczek["kwota_gr"] / 100.0
            
            st.markdown(f"**{o_czl}** ({o_kolo}) — **{o_kwota:.2f} zł** | Przelew: **{r_oczek['data_wplaty']}** | Zgłosił: {r_oczek['zglosil_nazwa']}")
            c_ak1, c_ak2 = st.columns([1, 1])
            with c_ak1:
                if st.button(f"✅ Akceptuj wpłatę #{o_id}", key=f"btn_akcept_{o_id}"):
                    teraz_akcept = teraz_utc()
                    idempotent_key = f"zaakceptowana_oczekujaca_{o_id}"
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO wplaty (kolo_id, czlonek_id, kwota_gr, data_wplaty, notatka, data_wpisu, idempotency_key)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (r_oczek["kolo_id"], r_oczek["czlonek_id"], r_oczek["kwota_gr"], r_oczek["data_wplaty"], r_oczek["notatka"], teraz_akcept, idempotent_key))
                            
                            cur.execute("""
                                UPDATE wplaty_oczekujace 
                                SET status = 'ZAAKCEPTOWANA', rozpatrzyl_uzytkownik_id = %s, data_rozpatrzenia = %s 
                                WHERE id = %s
                            """, (curr_user_id, teraz_akcept, o_id))
                        conn.commit()
                    st.cache_data.clear()
                    st.success("Zaksięgowano wpłatę.")
                    st.rerun()
            with c_ak2:
                with st.expander("❌ Odrzuć wpłatę"):
                    powod_odrzut = st.text_input("Powód odrzucenia:", value="Brak wpływu na wyciągu", key=f"txt_odrzuc_{o_id}")
                    if st.button("Potwierdź odrzucenie", key=f"btn_odrzuc_{o_id}"):
                        db_execute("""
                            UPDATE wplaty_oczekujace 
                            SET status = 'ODRZUCONA', rozpatrzyl_uzytkownik_id = %s, data_rozpatrzenia = %s, powod_odrzucenia = %s 
                            WHERE id = %s
                        """, (curr_user_id, teraz_utc(), powod_odrzut, o_id))
                        st.warning("Wpłata odrzucona.")
                        st.rerun()
            st.divider()

