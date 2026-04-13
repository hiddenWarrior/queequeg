from tests.fixtures.constructor_dep import MyService


def creates_in_loop():
    # MyService() called inside a for loop — called_names tracking must still work
    results = []
    for i in range(3):
        results.append(MyService())
    return results


def creates_in_try():
    # MyService() called inside a try block — same requirement
    try:
        return MyService()
    except Exception:
        return None
