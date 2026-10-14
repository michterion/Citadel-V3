import plotly.graph_objects as go
from config import pobierz_kolor_kdi

def render_wykres_salda(punkty_x, punkty_saldo):
    fig_saldo = go.Figure()
    fig_saldo.add_trace(go.Scatter(
        x=punkty_x, y=punkty_saldo, mode='lines+markers', name='Saldo',
        line=dict(color='#a855f7', width=3, shape='spline'),
        marker=dict(size=7, color='#c084fc', line=dict(color='#ffffff', width=1.5)),
        hovertemplate='Data: %{x}<br>Saldo: %{y:.2f} zł<extra></extra>'
    ))
    fig_saldo.add_hline(y=0, line_dash="solid", line_color="#ffffff", line_width=2,
                        annotation_text="0.00 zł (RÓWNOWAGA)", annotation_position="top left",
                        annotation_font_color="#ffffff", annotation_font_size=11)
    fig_saldo.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(21, 18, 38, 0.9)',
        margin=dict(l=20, r=20, t=30, b=20), height=360,
        xaxis=dict(showgrid=True, gridcolor='#262040', color='#94a3b8'),
        yaxis=dict(showgrid=True, gridcolor='#262040', color='#94a3b8'), hovermode="x unified"
    )
    return fig_saldo

def render_wykres_kdi(punkty_x, punkty_kdi):
    kolory_markerow_kdi = [pobierz_kolor_kdi(v) for v in punkty_kdi]
    fig_kdi = go.Figure()
    fig_kdi.add_trace(go.Scatter(
        x=punkty_x, y=punkty_kdi, mode='lines+markers', name='KDI',
        line=dict(color='#64748b', width=2.5, shape='spline'),
        marker=dict(size=8, color=kolory_markerow_kdi, line=dict(color='#ffffff', width=1.5)),
        connectgaps=False, hovertemplate='Data: %{x}<br>KDI: %{y:.2f}<extra></extra>'
    ))
    fig_kdi.add_hline(y=1.0, line_dash="solid", line_color="#ffffff", line_width=2,
                      annotation_text="1.00 (Cel 100%)", annotation_position="bottom left",
                      annotation_font_color="#ffffff", annotation_font_size=11)
    fig_kdi.add_hline(y=1.2, line_dash="dash", line_color="#facc15", line_width=2,
                      annotation_text="1.20 (Granica)", annotation_position="top left",
                      annotation_font_color="#facc15", annotation_font_size=11)
    valid_kdi = [v for v in punkty_kdi if v is not None]
    max_kdi = max(valid_kdi) if valid_kdi else 2.0
    fig_kdi.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(21, 18, 38, 0.9)',
        margin=dict(l=20, r=20, t=30, b=20), height=360,
        xaxis=dict(showgrid=True, gridcolor='#262040', color='#94a3b8'),
        yaxis=dict(showgrid=True, gridcolor='#262040', color='#94a3b8', range=[0.5, max(max_kdi + 0.5, 2.0)]),
        hovermode="x unified"
    )
    return fig_kdi