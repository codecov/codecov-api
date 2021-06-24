from ariadne import ObjectType

coverage_diff_bindable = ObjectType("CoverageDiff")

# The total structure is like so
# {
# "diff": [
# 1,                  //files count
# 0,                  //lines count
# 0,                  //hits count
# 0,                  //misses count
# 0,                  //partials count
# null,               //coverage (null or number)
# 0,                  //branches count
# 0,                  //methods count
# 0,                  //messages count
# 0,                  //sessions count
# null,               //complexity (null or number)
# null,               //complexity_total (null or number)
# ,0],                //diff
# }

# map a field to the index in the list, following the above structure
coverage_diff_bindable.field("coverage")(lambda diff, _: diff[5])
