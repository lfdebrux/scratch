from code_taxonomy import Search


def test_code_search(tmp_path):
    """Test the functioning of Search.search_for()"""
    # test fixtures
    (tmp_path / "test1.txt").write_text("Hello foo")
    (tmp_path / "test2.txt").write_text("Hello bar")
    (tmp_path / "test3.txt").write_text("Goodbye foobar")

    class Hello(Search):
        epic = "Hello"
        paths = (tmp_path,)
        pattern = r"Hello {name}"
        name = ".*"

    class HelloFoo(Hello):
        epic = "Hello foo"
        name = "foo"

    matches = list(Search.search_for([Hello, HelloFoo]))

    assert len(matches) == 2
    for match in matches:
        assert str(match["path"]).startswith(str(tmp_path))
        if match["path"].name == "test1.txt":
            assert match["epics"] == {"Hello foo"}
            assert match["lines"] == "Hello foo"
        elif match["path"].name == "test2.txt":
            assert match["epics"] == {"Hello"}
            assert match["lines"] == "Hello bar"
        else:
            assert match["path"].name != "test3.txt"
