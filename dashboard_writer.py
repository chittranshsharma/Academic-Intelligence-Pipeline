"""
Script to write dashboard.html — run once.
"""
html = open("dashboard_template.html", "r", encoding="utf-8").read()
with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
print("dashboard.html written")
