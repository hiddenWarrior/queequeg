from tests.fixtures.cross_file_b import shared_helper
from tests.fixtures.cross_file_b import helper


def dep_in_for_body():
    for i in range(10):
        shared_helper()


def dep_in_while_body():
    while True:
        return helper()


def dep_in_with_body():
    with open(__file__):
        return shared_helper()
