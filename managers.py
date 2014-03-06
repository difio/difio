################################################################################
#
#   Copyright David Cramer as seen on https://gist.github.com/550438
#
################################################################################



from django.db.models.query import QuerySet
from django.db.models.manager import Manager
from django.db.models.deletion import Collector

class QuerySetDoubleIteration(Exception):
    "A QuerySet was iterated over twice, you probably want to list() it."
    pass


# "Skinny" here means we use iterator by default, rather than
# ballooning in memory.
class SkinnyManager(Manager):
    def get_query_set(self):
        return SkinnyQuerySet(self.model, using=self._db)


class SkinnyQuerySet(QuerySet):
    def __len__(self):
        if getattr(self, 'has_run_before', False):
            raise TypeError("SkinnyQuerySet doesn't support __len__ after __iter__, if you *only* need a count you should use .count(), if you need to reuse the results you should coerce to a list and then len() that.")
        return super(SkinnyQuerySet, self).__len__()

    def __iter__(self):
        if self._result_cache is not None:
            # __len__ must have been run
            return iter(self._result_cache)

        has_run_before = getattr(self, 'has_run_before', False)
        if has_run_before:
            raise QuerySetDoubleIteration("This SkinnyQuerySet has already been iterated over once, you should assign it to a list if you want to reuse the data.")
        self.has_run_before = True

        return self.iterator()

    # override here b/c we can't patch Django in our PaaS environments
    # NB: doesn't execute the inherited method, copy full method definition
    # NB: Needs to be updated with every Django upgrade
    def delete(self):
        """
        Deletes the records in the current QuerySet.
        """
        assert self.query.can_filter(), \
                "Cannot use 'limit' or 'offset' with delete."

        # NB: this line is patched to work with SkinnyQuerySet
        # see https://gist.github.com/550438#file-gistfile2-txt
        del_query = self._clone(klass=QuerySet)

        # The delete is actually 2 queries - one to find related objects,
        # and one to delete. Make sure that the discovery of related
        # objects is performed on the same database as the deletion.
        del_query._for_write = True

        # Disable non-supported fields.
        del_query.query.select_for_update = False
        del_query.query.select_related = False
        del_query.query.clear_ordering(force_empty=True)

        collector = Collector(using=del_query.db)
        collector.collect(del_query)
        collector.delete()

        # Clear the result cache, in case this QuerySet gets reused.
        self._result_cache = None
    delete.alters_data = True
