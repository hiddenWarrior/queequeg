import tests.fixtures.cross_file_b as cfb


def uses_plain_import():
    return cfb.shared_helper()


def uses_plain_import_no_alias():
    import tests.fixtures.cross_file_b
    return tests.fixtures.cross_file_b.shared_helper()
