import graphene
import pytest

from .....product import ProductTypeKind
from .....product.models import ProductType
from ....tests.utils import (
    assert_no_permission,
    get_graphql_content,
    get_graphql_content_from_response,
)


def test_product_types(user_api_client, product_type, channel_USD):
    query = """
    query ($channel: String){
        productTypes(first: 20) {
            totalCount
            edges {
                node {
                    id
                    name
                    products(first: 1, channel: $channel) {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
    """
    variables = {"channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    no_product_types = ProductType.objects.count()
    assert content["data"]["productTypes"]["totalCount"] == no_product_types
    assert len(content["data"]["productTypes"]["edges"]) == no_product_types


@pytest.mark.parametrize(
    ("product_type_filter", "count"),
    [
        ({"configurable": "CONFIGURABLE"}, 2),  # has_variants
        ({"configurable": "SIMPLE"}, 1),  # !has_variants
        ({"productType": "SHIPPABLE"}, 2),  # is_shipping_required
        ({"kind": "NORMAL"}, 2),
        ({"kind": "GIFT_CARD"}, 1),
        ({"slugs": ["digital-type", "tools"]}, 2),
        ({"slugs": []}, 3),
    ],
)
def test_product_type_query_with_filter(
    product_type_filter, count, staff_api_client, permission_manage_products
):
    query = """
        query ($filter: ProductTypeFilterInput!, ) {
          productTypes(first:5, filter: $filter) {
            edges{
              node{
                id
                name
              }
            }
          }
        }
        """
    ProductType.objects.bulk_create(
        [
            ProductType(
                name="Digital Type",
                slug="digital-type",
                has_variants=True,
                is_shipping_required=False,
                kind=ProductTypeKind.NORMAL,
            ),
            ProductType(
                name="Tools",
                slug="tools",
                has_variants=True,
                is_shipping_required=True,
                kind=ProductTypeKind.NORMAL,
            ),
            ProductType(
                name="Books",
                slug="books",
                has_variants=False,
                is_shipping_required=True,
                kind=ProductTypeKind.GIFT_CARD,
            ),
        ]
    )

    variables = {"filter": product_type_filter}
    staff_api_client.user.user_permissions.add(permission_manage_products)
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    product_types = content["data"]["productTypes"]["edges"]

    assert len(product_types) == count


QUERY_PRODUCT_TYPES_WITH_SORT = """
    query ($sort_by: ProductTypeSortingInput!) {
        productTypes(first:5, sortBy: $sort_by) {
                edges{
                    node{
                        name
                    }
                }
            }
        }
"""


@pytest.mark.parametrize(
    ("product_type_sort", "result_order"),
    [
        ({"field": "NAME", "direction": "ASC"}, ["Digital", "Subscription", "Tools"]),
        ({"field": "NAME", "direction": "DESC"}, ["Tools", "Subscription", "Digital"]),
        # is_shipping_required
        (
            {"field": "SHIPPING_REQUIRED", "direction": "ASC"},
            ["Digital", "Subscription", "Tools"],
        ),
        (
            {"field": "SHIPPING_REQUIRED", "direction": "DESC"},
            ["Tools", "Subscription", "Digital"],
        ),
    ],
)
def test_product_type_query_with_sort(
    product_type_sort, result_order, staff_api_client, permission_manage_products
):
    ProductType.objects.bulk_create(
        [
            ProductType(
                name="Digital",
                slug="digital",
                has_variants=True,
                is_shipping_required=False,
            ),
            ProductType(
                name="Tools",
                slug="tools",
                has_variants=True,
                is_shipping_required=True,
            ),
            ProductType(
                name="Subscription",
                slug="subscription",
                has_variants=False,
                is_shipping_required=False,
            ),
        ]
    )

    variables = {"sort_by": product_type_sort}
    staff_api_client.user.user_permissions.add(permission_manage_products)
    response = staff_api_client.post_graphql(QUERY_PRODUCT_TYPES_WITH_SORT, variables)
    content = get_graphql_content(response)
    product_types = content["data"]["productTypes"]["edges"]

    for order, product_type_name in enumerate(result_order):
        assert product_types[order]["node"]["name"] == product_type_name


NOT_EXISTS_IDS_COLLECTIONS_QUERY = """
    query ($filter: ProductTypeFilterInput!) {
        productTypes(first: 5, filter: $filter) {
            edges {
                node {
                    id
                    name
                }
            }
        }
    }
"""


def test_product_types_query_ids_not_exists(user_api_client, category):
    query = NOT_EXISTS_IDS_COLLECTIONS_QUERY
    variables = {"filter": {"ids": ["fTEJRuFHU6fd2RU=", "2XwnQNNhwCdEjhP="]}}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response, ignore_errors=True)
    message_error = '{"ids":[{"message":"Invalid ID specified.","code":""}]}'

    assert len(content["errors"]) == 1
    assert content["errors"][0]["message"] == message_error
    assert content["data"]["productTypes"] is None


QUERY_FILTER_PRODUCT_TYPES = """
    query($filters: ProductTypeFilterInput) {
      productTypes(first: 10, filter: $filters) {
        edges {
          node {
            name
          }
        }
      }
    }
"""


@pytest.mark.parametrize(
    ("search", "expected_names"),
    [
        ("", ["The best juices", "The best beers", "The worst beers"]),
        ("best", ["The best juices", "The best beers"]),
        ("worst", ["The worst beers"]),
        ("average", []),
    ],
)
def test_filter_product_types_by_custom_search_value(
    api_client, search, expected_names
):
    query = QUERY_FILTER_PRODUCT_TYPES

    ProductType.objects.bulk_create(
        [
            ProductType(name="The best juices", slug="best-juices"),
            ProductType(name="The best beers", slug="best-beers"),
            ProductType(name="The worst beers", slug="worst-beers"),
        ]
    )

    variables = {"filters": {"search": search}}

    results = get_graphql_content(api_client.post_graphql(query, variables))["data"][
        "productTypes"
    ]["edges"]

    assert len(results) == len(expected_names)
    matched_names = sorted([result["node"]["name"] for result in results])

    assert matched_names == sorted(expected_names)


QUERY_FILTER_PRODUCT_TYPES_WITH_SLUGS = """
    query($filters: ProductTypeFilterInput) {
      productTypes(first: 10, filter: $filters) {
        edges {
          node {
            slug
          }
        }
      }
    }
"""


@pytest.mark.parametrize(
    ("_case", "tax_class_indexes", "expected_product_type_indexes"),
    [
        ("single_tax_class", [0], [0, 1]),
        ("multiple_tax_classes", [0, 1], [0, 1, 2]),
    ],
)
def test_filter_product_types_by_tax_classes(
    _case,
    tax_class_indexes,
    expected_product_type_indexes,
    staff_api_client,
    product_type_list,
    tax_classes,
):
    # given
    product_types = list(product_type_list)
    product_types[0].tax_class = tax_classes[0]
    product_types[1].tax_class = tax_classes[0]
    product_types[2].tax_class = tax_classes[1]
    ProductType.objects.bulk_update(product_types, ["tax_class"])

    variables = {
        "filters": {
            "taxClasses": [
                graphene.Node.to_global_id("TaxClass", tax_classes[index].pk)
                for index in tax_class_indexes
            ]
        }
    }

    # when
    response = staff_api_client.post_graphql(
        QUERY_FILTER_PRODUCT_TYPES_WITH_SLUGS, variables
    )

    # then
    content = get_graphql_content(response)
    edges = content["data"]["productTypes"]["edges"]
    assert len(edges) == len(expected_product_type_indexes)
    assert {edge["node"]["slug"] for edge in edges} == {
        product_types[index].slug for index in expected_product_type_indexes
    }


def test_filter_product_types_by_tax_classes_null(api_client, product_type_list):
    # given
    variables = {"filters": {"taxClasses": None}}

    # when
    response = api_client.post_graphql(
        QUERY_FILTER_PRODUCT_TYPES_WITH_SLUGS, variables
    )

    # then
    content = get_graphql_content(response)
    edges = content["data"]["productTypes"]["edges"]
    assert len(edges) == len(product_type_list)
    assert {edge["node"]["slug"] for edge in edges} == {
        product_type.slug for product_type in product_type_list
    }


@pytest.mark.parametrize(
    ("_case", "client_fixture", "is_allowed"),
    [
        ("Unauthenticated user should be rejected", "api_client", False),
        (
            "Authenticated unprivileged user (non-staff) should be rejected",
            "user_api_client",
            False,
        ),
        (
            "Authenticated staff user w/o permissions should be allowed",
            "staff_api_client",
            True,
        ),
        ("Authenticated app w/o permissions should be allowed", "app_api_client", True),
    ],
)
def test_filter_product_types_by_tax_classes_authorization(
    _case, client_fixture, is_allowed, request, product_type_list, tax_classes
):
    # given
    client = request.getfixturevalue(client_fixture)
    tax_class = tax_classes[0]
    product_type = product_type_list[0]
    product_type.tax_class = tax_class
    product_type.save(update_fields=["tax_class"])

    variables = {
        "filters": {
            "taxClasses": [graphene.Node.to_global_id("TaxClass", tax_class.pk)]
        }
    }

    # when
    response = client.post_graphql(QUERY_FILTER_PRODUCT_TYPES_WITH_SLUGS, variables)

    # then
    if is_allowed:
        content = get_graphql_content(response)
        assert content["data"]["productTypes"]["edges"] == [
            {"node": {"slug": product_type.slug}}
        ]
    else:
        assert_no_permission(response)
        content = get_graphql_content_from_response(response)
        assert len(content["errors"]) == 1
        assert content["errors"][0]["message"] == (
            "To access this path, you need one of the following permissions: "
            "AUTHENTICATED_STAFF_USER, AUTHENTICATED_APP"
        )
        assert content["data"]["productTypes"] is None
