import pytest

from toolchains.common import triplet_field


def test_0_filed() -> None:
    with pytest.raises(RuntimeError):
        triplet_field("")


def test_1_filed() -> None:
    with pytest.raises(RuntimeError):
        triplet_field("x86_64")


def test_2_field() -> None:
    fields = triplet_field("x86_64-elf")
    assert fields.arch == "x86_64"
    assert fields.vendor == "unknown"
    assert fields.os == "unknown"
    assert fields.abi == "elf"


def test_3_field() -> None:
    fields = triplet_field("x86_64-linux-gnu")
    assert fields.arch == "x86_64"
    assert fields.vendor == "unknown"
    assert fields.os == "linux"
    assert fields.abi == "gnu"

    fields = triplet_field("arm-none-eabi")
    assert fields.arch == "arm"
    assert fields.vendor == "unknown"
    assert fields.os == "none"
    assert fields.abi == "eabi"

    fields = triplet_field("x86_64-nonewlib-elf")
    assert fields.arch == "x86_64"
    assert fields.vendor == "nonewlib"
    assert fields.os == "unknown"
    assert fields.abi == "elf"


def test_4_field() -> None:
    fields = triplet_field("x86_64-pc-linux-gnu")
    assert fields.arch == "x86_64"
    assert fields.vendor == "pc"
    assert fields.os == "linux"
    assert fields.abi == "gnu"


def test_field_check() -> None:
    assert triplet_field.check("") == False
    assert triplet_field.check("x86_64") == False
    assert triplet_field.check("x86_64-") == False
    assert triplet_field.check("x86_64--") == False
    assert triplet_field.check("x86_64---") == False
    assert triplet_field.check("x86_64-elf") == True


def test_drop_vendor() -> None:
    assert triplet_field("x86_64-pc-linux-gnu").drop_vendor() == "x86_64-linux-gnu"


def test_weak_eq() -> None:
    assert triplet_field("x86_64-linux-gnu").weak_eq(triplet_field("x86_64-pc-linux-gnu"))
    assert not triplet_field("x86_64-linux-gnu").weak_eq(triplet_field("x86_64-linux-musl"))
    assert not triplet_field("x86_64-linux-gnu").weak_eq(triplet_field("x86_64-pc-linux-musl"))


def test_normalize() -> None:
    fields = triplet_field("arm-none-eabi", True)
    assert fields.arch == "arm"
    assert fields.vendor == "unknown"
    assert fields.os == "unknown"
    assert fields.abi == "eabi"
