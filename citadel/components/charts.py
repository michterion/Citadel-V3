import plotly.graph_objects as go
from config import pobierz_kolor_kdi

PLOTLY_CONFIG = {
    'displayModeBar': False,
    'responsive': True
}

def render_wykres_salda(punkty_x, punkty_saldo):
    """
    Wykres osi czasu salda:
    - Bez pojedynczych markerów/punktów (gładka linia spline).
    - Dynamiczne kolorowanie (zielony: dodatnie, biały: neutralne, czerwony: ujemne).
    - Wielowarstwowa neonowa poświata linii.
    - Półprzezroczyste wypełnienie znajdujące się ZAWSZE POD wykresem (tonexty do dolnej krawędzi).
    """
    fig = go.Figure()

    if not punkty_saldo or not punkty_x:
        return fig

    # Określenie statusu salda (bieżące/końcowe saldo na osi)
    ostatnie_saldo = punkty_saldo[-1]
    if ostatnie_saldo > 0.001:
        # Dodatnie: Szmaragdowy / Neon Green
        kolor_glowny = '#22c55e'
        kolor_poswiaty_mid = 'rgba(34, 197, 94, 0.40)'
        kolor_poswiaty_outer = 'rgba(34, 197, 94, 0.16)'
        kolor_wypelnienia = 'rgba(34, 197, 94, 0.08)'
        kolor_akcentu = '#22c55e'
    elif ostatnie_saldo < -0.001:
        # Ujemne: Koralowy / Neon Red
        kolor_glowny = '#ef4444'
        kolor_poswiaty_mid = 'rgba(239, 68, 68, 0.40)'
        kolor_poswiaty_outer = 'rgba(239, 68, 68, 0.16)'
        kolor_wypelnienia = 'rgba(239, 68, 68, 0.08)'
        kolor_akcentu = '#ef4444'
    else:
        # Neutralne: Czysta biel
        kolor_glowny = '#ffffff'
        kolor_poswiaty_mid = 'rgba(255, 255, 255, 0.35)'
        kolor_poswiaty_outer = 'rgba(255, 255, 255, 0.14)'
        kolor_wypelnienia = 'rgba(255, 255, 255, 0.06)'
        kolor_akcentu = '#ffffff'

    # Obliczenie granic osi Y, tak by wypełnienie było zawsze pod krzywą
    min_saldo = min(punkty_saldo)
    max_saldo = max(punkty_saldo)
    rozstep = max_saldo - min_saldo
    margines = max(rozstep * 0.15, 30.0)

    y_dol = min(min_saldo, 0.0) - margines
    y_gora = max(max_saldo, 0.0) + margines

    # 1. Niewidoczna linia bazowa na samym dole wykresu (podstawa do wypełnienia pod wykresem)
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=[y_dol] * len(punkty_x),
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)'),
        hoverinfo='skip',
        showlegend=False
    ))

    # 2. Półprzezroczyste wypełnienie pod wykresem (od krzywej w dół do linii bazowej)
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_saldo,
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)', shape='spline'),
        fill='tonexty',
        fillcolor=kolor_wypelnienia,
        hoverinfo='skip',
        showlegend=False
    ))

    # 3. Zewnętrzna szeroka poświata neonowa
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_saldo,
        mode='lines',
        line=dict(color=kolor_poswiaty_outer, width=8, shape='spline'),
        hoverinfo='skip',
        showlegend=False
    ))

    # 4. Środkowa poświata neonowa
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_saldo,
        mode='lines',
        line=dict(color=kolor_poswiaty_mid, width=4.5, shape='spline'),
        hoverinfo='skip',
        showlegend=False
    ))

    # 5. Ostra linia główna (bez markerów - chyba że jest dokładnie 1 punkt)
    is_single_point = len(punkty_saldo) == 1
    mode_glowny = 'markers' if is_single_point else 'lines'
    marker_dict = dict(size=8, color=kolor_glowny, line=dict(color='#ffffff', width=2)) if is_single_point else None

    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_saldo,
        mode=mode_glowny,
        name='Saldo',
        line=dict(color=kolor_glowny, width=2.2, shape='spline'),
        marker=marker_dict,
        hovertemplate='Data: %{x}<br><b>Saldo: %{y:,.2f} zł</b><extra></extra>'
    ))

    # Linia równowagi 0.00 zł
    fig.add_hline(
        y=0,
        line_dash="dot",
        line_color="rgba(255, 255, 255, 0.4)",
        line_width=1.2,
        annotation_text="0.00 zł (Równowaga)",
        annotation_position="top left",
        annotation_font=dict(color="rgba(255, 255, 255, 0.75)", size=10, family="Inter, sans-serif")
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(21, 18, 38, 0.65)',
        font=dict(family='Inter, sans-serif'),
        margin=dict(l=20, r=20, t=30, b=25),
        height=360,
        xaxis=dict(
            showgrid=False,
            color='#94a3b8',
            tickfont=dict(size=11, family='Inter, sans-serif'),
            showspikes=True,
            spikethickness=1,
            spikedash='dot',
            spikecolor=kolor_akcentu,
            spikemode='across'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            color='#94a3b8',
            ticksuffix=' zł',
            tickformat=',.2f',
            range=[y_dol, y_gora],
            tickfont=dict(size=11, family='Inter, sans-serif')
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor='#191430',
            bordercolor=kolor_akcentu,
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12)
        )
    )
    return fig

def render_wykres_kdi(punkty_x, punkty_kdi):
    """
    Wykres dynamiki wskaźnika KDI:
    - Bez punktów (gładka linia neonowa).
    - Czyste tło bez prostokątów i bez linii adnotacyjnych.
    - Dynamiczne kolorowanie wg KDI: zielony (<= 1.0), żółty (1.0-1.2), czerwony (> 1.2), biały (brak).
    """
    valid_kdi = [v for v in punkty_kdi if v is not None]
    max_kdi = max(valid_kdi) if valid_kdi else 2.0
    y_max = max(max_kdi + 0.35, 1.8)

    # Dynamiczne kolorowanie KDI:
    # <= 1.00: Zielony neon (wzorowy / pełne opłacenie)
    # 1.00 - 1.20: Żółty neon (w normie / granica karencji)
    # > 1.20: Czerwony neon (przekroczona norma / utrata prawa głosu)
    # None: Biały
    ostatnie_kdi = valid_kdi[-1] if valid_kdi else None
    if ostatnie_kdi is None:
        kolor_kdi = '#ffffff'
        r, g, b = 255, 255, 255
    elif ostatnie_kdi <= 1.00:
        kolor_kdi = '#22c55e'
        r, g, b = 34, 197, 94
    elif ostatnie_kdi <= 1.20:
        kolor_kdi = '#facc15'
        r, g, b = 250, 204, 21
    else:
        kolor_kdi = '#ef4444'
        r, g, b = 239, 68, 68

    kolor_poswiaty_mid = f'rgba({r}, {g}, {b}, 0.38)'
    kolor_poswiaty_outer = f'rgba({r}, {g}, {b}, 0.16)'
    kolor_wypelnienia = f'rgba({r}, {g}, {b}, 0.08)'

    fig = go.Figure()

    # 1. Niewidoczna linia bazowa na dole wykresu (y=0) dla wypełnienia
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=[0.0] * len(punkty_x),
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)'),
        hoverinfo='skip',
        showlegend=False
    ))

    # 2. Półprzezroczyste wypełnienie pod wykresem w kolorze bieżącego KDI
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_kdi,
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)', shape='spline'),
        fill='tonexty',
        fillcolor=kolor_wypelnienia,
        connectgaps=False,
        hoverinfo='skip',
        showlegend=False
    ))

    # 3. Zewnętrzna szeroka poświata neonowa
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_kdi,
        mode='lines',
        line=dict(color=kolor_poswiaty_outer, width=8, shape='spline'),
        connectgaps=False,
        hoverinfo='skip',
        showlegend=False
    ))

    # 4. Środkowa poświata neonowa
    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_kdi,
        mode='lines',
        line=dict(color=kolor_poswiaty_mid, width=4.5, shape='spline'),
        connectgaps=False,
        hoverinfo='skip',
        showlegend=False
    ))

    # 5. Główna ostra linia neonowa (bez markerów/punktów)
    is_single_point = len(valid_kdi) == 1
    mode_glowny = 'markers' if is_single_point else 'lines'
    marker_dict = dict(size=8, color=kolor_kdi, line=dict(color='#ffffff', width=2)) if is_single_point else None

    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_kdi,
        mode=mode_glowny,
        name='KDI',
        line=dict(color=kolor_kdi, width=2.2, shape='spline'),
        marker=marker_dict,
        connectgaps=False,
        hovertemplate='Data: %{x}<br><b>KDI: %{y:.2f}</b><extra></extra>'
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(21, 18, 38, 0.65)',
        font=dict(family='Inter, sans-serif'),
        margin=dict(l=20, r=20, t=30, b=25),
        height=360,
        xaxis=dict(
            showgrid=False,
            color='#94a3b8',
            tickfont=dict(size=11, family='Inter, sans-serif'),
            showspikes=True,
            spikethickness=1,
            spikedash='dot',
            spikecolor=kolor_kdi,
            spikemode='across'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            color='#94a3b8',
            range=[0, y_max],
            tickformat='.2f',
            tickfont=dict(size=11, family='Inter, sans-serif')
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor='#191430',
            bordercolor=kolor_kdi,
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12)
        )
    )
    return fig

def render_wykres_slupkowy_kdi(elementy, tytul_x="Wskaźnik KDI"):
    """
    Lekki poziomy wykres słupkowy KDI dla kół lub regionów z linią graniczną 1.20.
    elementy: lista słowników [{'nazwa': str, 'kdi': float}]
    """
    if not elementy:
        return None

    prawidlowe = [e for e in elementy if e.get("kdi") is not None]
    if not prawidlowe:
        return None

    # Sortuj malejąco, by w poziomym wykresie (rysowanym od dołu) najlepsze KDI były u góry
    prawidlowe_posortowane = sorted(prawidlowe, key=lambda x: x["kdi"], reverse=True)

    y_labels = [p["nazwa"] for p in prawidlowe_posortowane]
    x_values = [p["kdi"] for p in prawidlowe_posortowane]
    colors = [pobierz_kolor_kdi(v) for v in x_values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=y_labels,
        x=x_values,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(color='rgba(255, 255, 255, 0.15)', width=1)
        ),
        hovertemplate='<b>%{y}</b><br>KDI: %{x:.2f}<extra></extra>'
    ))

    # Pionowa linia graniczna 1.20
    fig.add_vline(
        x=1.20,
        line_dash="dash",
        line_color="#facc15",
        line_width=1.5,
        annotation_text="1.20 (Granica)",
        annotation_position="top right",
        annotation_font=dict(color="#facc15", size=10, family="Inter, sans-serif")
    )

    # Oblicz dynamiczną wysokość, by wykres był kompaktowy
    wysokosc = max(220, min(500, len(prawidlowe_posortowane) * 36 + 60))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(21, 18, 38, 0.65)',
        font=dict(family='Inter, sans-serif'),
        margin=dict(l=15, r=15, t=25, b=25),
        height=wysokosc,
        xaxis=dict(
            title=dict(text=tytul_x, font=dict(color='#94a3b8', size=11)),
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            color='#94a3b8',
            tickformat='.2f',
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            showgrid=False,
            color='#f1f5f9',
            tickfont=dict(size=12)
        ),
        hoverlabel=dict(
            bgcolor='#191430',
            bordercolor='#6366f1',
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12)
        )
    )
    return fig