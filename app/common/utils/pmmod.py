import typing
import app.common.utils as utils


def pmmod_desc(pmmod: int) -> list:
    pmmod_str: str = str(pmmod)
    pm_length: int = len(pmmod_str)
    result: list[tuple] = []
    for target_pmmod_index in range(pm_length):
        z = int(pmmod_str[target_pmmod_index])
        result.append(tuple(map(bool, (4 & z, 2 & z, 1 & z))))
    return result


def pmmod_calc(pmmod: typing.Iterable[typing.Iterable[int]]) -> int:
    if not pmmod:
        raise ValueError('Argument \'pmmod\' is empty')

    pmmod_element_check = lambda z: utils.isiterable(z)\
                                and (not isinstance(z, (str, bytes)))\
                                and len(z) == 3  # noqa
    if not all(map(pmmod_element_check, pmmod)):
        raise ValueError('Length of one of argument \'pmmod\' elements is not 3')

    result: str = ''
    for pmmod_element in pmmod:
        result += str(int(''.join(map(lambda z: str(int(bool(z))), pmmod_element)), 2))

    return int(result)
