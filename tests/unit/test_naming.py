from minipaas.common import naming


def test_constants():
    assert naming.RESOURCE_PREFIX == "minipaas-"
    assert naming.LABEL_MANAGED == "minipaas.managed"
    assert naming.LABEL_COMPONENT == "minipaas.component"
