from ariadne import ObjectType

coverage_totals_bindable = ObjectType("CoverageTotals")

# The total structure is like so
# {
#   "totals": {
#     "c": "70.00000",  // coverage ratio
#     "f": 2,               // files count
#     "n": 10,          // lines count
#     "h": 7,           // hits count
#     "m": 2,           // missed count
#     "p": 1,           // partials count
#     "b": 3,           // branches count
#     "d": 0,           // methods count
#     "M": 0,           // messages count
#     "s": 3            // sessions count
#   }
# }

coverage_totals_bindable.set_alias("coverage", "c")
coverage_totals_bindable.set_alias("fileCount", "f")
coverage_totals_bindable.set_alias("lineCount", "n")
coverage_totals_bindable.set_alias("hitsCount", "h")
coverage_totals_bindable.set_alias("missesCount", "m")
coverage_totals_bindable.set_alias("partialsCount", "p")
