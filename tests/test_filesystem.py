from app.tools.filesystem import (
    edit_file,
    list_directory,
    read_file,
    search_files,
    write_file,
)


def test_write_and_read_file(tmp_path):
    file_path = tmp_path / "hello.txt"

    write_result = write_file(
        str(file_path),
        "Hello from JARVIS",
    )

    assert "success" in write_result.lower()
    assert file_path.exists()

    content = read_file(str(file_path))

    assert "Hello from JARVIS" in content


def test_edit_file(tmp_path):
    file_path = tmp_path / "edit_test.txt"

    write_file(
        str(file_path),
        "Hello from JARVIS",
    )

    result = edit_file(
        str(file_path),
        "Hello from JARVIS",
        "Hello, world!",
    )

    assert "success" in result.lower()

    content = read_file(str(file_path))

    assert content == "Hello, world!"


def test_edit_file_requires_existing_text(tmp_path):
    file_path = tmp_path / "edit_test.txt"

    write_file(
        str(file_path),
        "Original content",
    )

    result = edit_file(
        str(file_path),
        "This text does not exist",
        "New content",
    )

    assert "error" in result.lower()

    content = read_file(str(file_path))

    assert content == "Original content"


def test_list_directory(tmp_path):
    file_path = tmp_path / "example.txt"

    write_file(
        str(file_path),
        "test",
    )

    result = list_directory(str(tmp_path))

    assert "example.txt" in result


def test_search_files(tmp_path):
    source_file = tmp_path / "example.py"

    write_file(
        str(source_file),
        "class Example:\n    pass\n",
    )

    result = search_files(
        str(tmp_path),
        "class Example",
    )

    assert "example.py" in result