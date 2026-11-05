"""Client presentations (O01): SYZ-template PowerPoint decks built in pure Python.

python-pptx cannot run on these machines (its lxml DLL is blocked by group
policy), so `ooxml` writes the PresentationML itself on top of the real
`apps/S00/S00_template.pptx`: genuine master, layouts, disclaimer and offices page.

    ooxml      the .pptx writer: slides from template layouts, text, tables, native charts
    charts     chart parts (doughnut, bar, line over dates, payoff scatter) with embedded data
    sources    term extraction from HTML factsheets/pricers, Yahoo market and fund data
    analytics  performance, risk, structured-product status and portfolio concentration
    builder    the two deck types: structured-product review and client portfolio review
    qc         reads a finished .pptx back and checks geometry, fonts, charts and data flags
"""
