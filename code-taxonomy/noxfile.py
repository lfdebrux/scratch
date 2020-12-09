import nox


@nox.session
def test(session):
    session.install("pytest", "pytest-flake8", "pytest-mypy")
    session.install(".")
    session.run("pytest", "test_code_taxonomy.py")


@nox.session
def format(session):
    session.install("black")
    session.run("black", ".")
