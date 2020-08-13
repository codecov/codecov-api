from django_filters import rest_framework as django_filters


class StringListFilter(django_filters.Filter):
    def __init__(self, query_param, *args, **kwargs):
        super(StringListFilter, self).__init__(*args, **kwargs)
        self.query_param = query_param

    def filter(self, qs, value):
        try:
            request = self.parent.request
        except AttributeError:
            return None

        values = request.GET.getlist(self.query_param)
        if len(values) > 0:
            return qs.filter(**{'%s__%s'%(self.field_name, self.lookup_expr):values})

        return qs