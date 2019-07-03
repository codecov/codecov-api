
class CommitsComparison(object):
    pass


class CompareViewMixin(object):

    def get_commits(self):
        raise NotImplementedError()
