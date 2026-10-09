import django_filters
import graphene
from django.db.models import Q

from saleor.graphql.warehouse.types import DEPRECATED_IN_3X_INPUT

from ....product.models import ProductType
from ...core.descriptions import ADDED_IN_324
from ...core.doc_category import DOC_CATEGORY_PRODUCTS
from ...core.filters import (
    EnumFilter,
    FilterInputObjectType,
    GlobalIDMultipleChoiceFilter,
    ListObjectTypeFilter,
    MetadataFilterBase,
)
from ...utils import resolve_global_ids_to_primary_keys
from ...utils.filters import filter_slug_list
from ..enums import (
    ProductTypeConfigurable,
    ProductTypeEnum,
    ProductTypeKindEnum,
)


def filter_product_type_configurable(qs, _, value):
    if value == ProductTypeConfigurable.CONFIGURABLE:
        qs = qs.filter(has_variants=True)
    elif value == ProductTypeConfigurable.SIMPLE:
        qs = qs.filter(has_variants=False)
    return qs


def filter_product_type(qs, _, value):
    if value == ProductTypeEnum.SHIPPABLE:
        qs = qs.filter(is_shipping_required=True)
    return qs


def filter_product_type_kind(qs, _, value):
    if value:
        qs = qs.filter(kind=value)
    return qs


def filter_product_type_tax_classes(qs, _, value):
    if not value:
        return qs
    _, tax_class_pks = resolve_global_ids_to_primary_keys(value, "TaxClass")
    return qs.filter(tax_class_id__in=tax_class_pks)


class ProductTypeFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method="filter_product_type_searchable")

    configurable = EnumFilter(
        input_class=ProductTypeConfigurable,
        method=filter_product_type_configurable,
        help_text=(
            f"{DEPRECATED_IN_3X_INPUT} The field has no effect on the API behavior. "
            "This is a leftover from the past Simple/Configurable product distinction. "
            "Products can have multiple variants regardless of this setting. "
        ),
    )

    product_type = EnumFilter(input_class=ProductTypeEnum, method=filter_product_type)
    kind = EnumFilter(input_class=ProductTypeKindEnum, method=filter_product_type_kind)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")
    slugs = ListObjectTypeFilter(input_class=graphene.String, method=filter_slug_list)
    tax_classes = GlobalIDMultipleChoiceFilter(
        method=filter_product_type_tax_classes,
        help_text=(
            "Filter by the tax classes assigned to product types. "
            "Requires an authenticated staff user or app." + ADDED_IN_324
        ),
    )

    class Meta:
        model = ProductType
        fields = ["search", "configurable", "product_type"]

    @classmethod
    def filter_product_type_searchable(cls, queryset, _name, value):
        if not value:
            return queryset
        name_slug_qs = Q(name__ilike=value) | Q(slug__ilike=value)
        return queryset.filter(name_slug_qs)


class ProductTypeFilterInput(FilterInputObjectType):
    class Meta:
        doc_category = DOC_CATEGORY_PRODUCTS
        filterset_class = ProductTypeFilter
