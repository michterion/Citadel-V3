import plotly.graph_objects as go
from config import pobierz_kolor_kdi

PLOTLY_CONFIG = {
    'displayModeBar': False,
    'responsive': True
}

def render_wykres_salda(punkty_x, punkty_saldo):
    """
    Nowoczesny wykres osi czasu salda z gradientowym wypełnieniem (area chart)
    i czystą typografią.
    """
    fig = go.Figure()

    is_compact = len(punkty_x) <= 35
    mode = 'lines+markers' if is_compact else 'lines'

    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_saldo,
        mode=mode,
        name='Saldo',
        line=dict(color='#a855f7', width=2.5, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(168, 85, 247, 0.12)',
        marker=dict(size=6, color='#c084fc', line=dict(color='#ffffff', width=1.5)) if is_compact else None,
        hovertemplate='Data: %{x}<br><b>Saldo: %{y:,.2f} zł</b><extra></extra>'
    ))

    # Pozioma linia równowagi 0.00 zł
    fig.add_hline(
        y=0,
        line_dash="solid",
        line_color="rgba(255, 255, 255, 0.7)",
        line_width=1.5,
        annotation_text="0.00 zł (Równowaga)",
        annotation_position="top left",
        annotation_font=dict(color="#ffffff", size=10, family="Inter, sans-serif")
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
            spikecolor='#818cf8',
            spikemode='across'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            color='#94a3b8',
            ticksuffix=' zł',
            tickformat=',.2f',
            tickfont=dict(size=11, family='Inter, sans-serif')
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor='#191430',
            bordercolor='#a855f7',
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12)
        )
    )
    return fig

def render_wykres_kdi(punkty_x, punkty_kdi):
    """
    Wykres dynamiki wskaźnika KDI z kolorystycznymi strefami decyzyjnymi
    (zielona: wzorowa, żółta: dopuszczalna, czerwona: karencja).
    """
    valid_kdi = [v for v in punkty_kdi if v is not None]
    max_kdi = max(valid_kdi) if valid_kdi else 2.0
    y_max = max(max_kdi + 0.35, 1.8)

    fig = go.Figure()

    # Subtelne strefy decyzyjne w tle
    fig.add_hrect(y0=0.0, y1=1.0, fillcolor='rgba(16, 185, 129, 0.05)', line_width=0, layer="below")
    fig.add_hrect(y0=1.0, y1=1.2, fillcolor='rgba(250, 204, 21, 0.05)', line_width=0, layer="below")
    fig.add_hrect(y0=1.2, y1=y_max + 1.0, fillcolor='rgba(239, 68, 68, 0.05)', line_width=0, layer="below")

    # Poziome linie graniczne
    fig.add_hline(
        y=1.0,
        line_dash="dot",
        line_color="#10b981",
        line_width=1.5,
        annotation_text="1.00 (Cel statutowy)",
        annotation_position="bottom left",
        annotation_font=dict(color="#10b981", size=10, family="Inter, sans-serif")
    )
    fig.add_hline(
        y=1.2,
        line_dash="dash",
        line_color="#facc15",
        line_width=1.5,
        annotation_text="1.20 (Granica prawa głosu)",
        annotation_position="top left",
        annotation_font=dict(color="#facc15", size=10, family="Inter, sans-serif")
    )

    is_compact = len(punkty_x) <= 35
    mode = 'lines+markers' if is_compact else 'lines'

    kolory_markerow = [pobierz_kolor_kdi(v) for v in punkty_kdi] if is_compact else None

    fig.add_trace(go.Scatter(
        x=punkty_x,
        y=punkty_kdi,
        mode=mode,
        name='KDI',
        line=dict(color='#38bdf8', width=2.5, shape='spline'),
        marker=dict(size=7, color=kolory_markerow, line=dict(color='#ffffff', width=1.5)) if is_compact else None,
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
            spikecolor='#38bdf8',
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
            bordercolor='#38bdf8',
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