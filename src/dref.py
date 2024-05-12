"""
Used for:
Decoding drefs, i.e `<d ref="Unit,fElder,MaxShields"/>` => '1024'
removing color tags and replacing sc2 new line tag (</n>) with \n
Note: doesn't decode strings with `$` in dref, since those indicate dynamic values
"""
import logging
import re
import typing
import numexpr # type: ignore

import sc2_globals
import xml_helper
import utils

logger = logging.getLogger(__name__)
dref_pattern = re.compile(r'<d\s+ref\s*=\s*"[^"]*"[^/>]*/>')


def strip_color(text: str) -> str:
    return re.sub(r'</?c\s*/?[^>]*>', '', text)


def replace_newlines(text: str) -> str:
    return re.sub(r'<\/?n\/?>', '\n', text)


def strip_leading_newlines(text: str) -> str:
    return re.sub(r'^(<\/?n\/?>)+', '', text)


def dynamic_dref(dref: str) -> bool:
    if any(expr in dref for expr in ['$', '%AMOUNT%']):
        return True
    return False


def contains_dref(text: str) -> bool:
    """
    checks based on what sc2/editor accepts as a dref
    """
    return dref_pattern.search(text) is not None


def extract_drefs(text: str) -> typing.Generator[str, None, None]:
    matches = dref_pattern.finditer(text)
    for m in matches:
        yield m.group()


def calculate_dref(dref: str, default: str = ' ') -> str:
    """
    returns numeric value as string if valid, otherwise default.

    example input:
    <d ref="(1-Behavior,SolidPlating,DamageResponse.ModifyFraction)*100" precision="1"/>
    """
    # "(1-Behavior,SolidPlating,DamageResponse.ModifyFraction)*100"
    s = re.search(r'"[^"]+"', dref)

    if s is not None:
        content = s.group().replace('"', '')
    # (1-Behavior,SolidPlating,DamageResponse.ModifyFraction)*100
    content = content.replace(' ', '') # final expression
    refs = re.split(r'[-+*/()]', content)
    # Behavior,SolidPlating,DamageResponse.ModifyFraction
    refs = [r for r in refs if r and not utils.is_number(r)]
    for ref in refs:
        ref_copy = ref
        # Behavior
        catalog = ref_copy.split(',', maxsplit=1)[0]
        root = sc2_globals.xml_roots_mapping[catalog]
        # SolidPlating,DamageResponse.ModifyFraction
        ref_copy = ref_copy.replace(f'{catalog},', '', 1)
        # SolidPlating
        entry_id = ref_copy.split(',')[0]
        entry = xml_helper.get_entry(root, entry_id)
        if entry is None:
            logger.warning('Invalid entry id: %s', entry_id)
            return default
        # DamageResponse.ModifyFraction (further splitting is done by xml parser)
        path = ref_copy.replace(f'{entry_id},', '')
        val = xml_helper.get_value(entry, root, path, default)
        content = content.replace(ref, val, 1)

    try:
        calc = numexpr.evaluate(content)
        if utils.is_number(calc):
            num = float(calc)
    except (SyntaxError, KeyError, ValueError) as e:
        logger.warning('Invalid dref expression %s: %s', dref, e.args)
        return default
    return f'{num:.2f}'


def decode_dref_string(text: typing.Optional[str], strip_tags: bool = True) -> str:
    """
    calculates any dref expression and puts value back into string
    if expression fails dref will be replaced by 1 whitespace
    """
    if not text:
        return ''
    if not contains_dref(text):
        logger.debug('%s doesn\'t contain dref', text)
    else:
        drefs = extract_drefs(text)
        for dref in drefs:
            if dynamic_dref(dref):
                logger.debug('$ found inside %s, skip decoding', dref)
                continue
            decoded = calculate_dref(dref)
            text = text.replace(dref, decoded)
    if strip_tags:
        text = strip_color(text)
        text = replace_newlines(text)
    return text
