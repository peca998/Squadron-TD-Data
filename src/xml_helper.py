"""
xml utils for easier parsing of sc2 data xml files
"""
import xml.etree.ElementTree
import xml.dom.minidom
import typing
import logging
import pathlib
import re

import utils

Element = xml.etree.ElementTree.Element
logger = logging.getLogger(__name__)

with open(pathlib.Path(__file__).parent.parent.resolve() / 'data/documentation/array_fields.txt', 'r', encoding='utf-8') as fp:
    data = fp.read()
gArrayFields = {s.strip() for s in data.split(',')}


def elem_has_subtag(elem: Element, tag: str) -> bool:
    return elem.find(tag) is not None


def elem_is_array(tag: str) -> bool:
    return tag in gArrayFields


def elem_is_named_array(elem: Element) -> bool:
    if not elem_is_array(elem.tag):
        return False
    index = elem.get('index')
    if index:
        if utils.is_number(index):
            return False
        return True
    return False


def elem_is_indexed_array(elem: Element) -> bool:
    if not elem_is_array(elem.tag):
        return False
    index = elem.get('index')
    if not index:
        return True
    return False


def get_attr(entry: Element, root: Element, tag_path: str, key: str) -> typing.Optional[str]:
    el = entry.find(tag_path)
    if el is None:
        # very special case... consider referencing core.sc2mod to avoid this and other defaults
        if tag_path == 'DisplayEffect':
            return entry.get('id')
        parent = get_parent(entry, root)
        if parent is not None:
            return get_attr(parent, root, tag_path, key)
        return get_default(entry.tag, tag_path)
    return el.attrib.get(key)


def get_array_elem(entry: Element, root: Element, tag_path: str, index: int) -> typing.Optional[Element]:
    """
    handles numeric based arrays
    """
    elems = entry.findall(tag_path)
    if not elems:
        parent = get_parent(entry, root)
        if parent is not None:
            return get_array_elem(parent, root, tag_path, index)
        return None
    if index > len(elems) - 1:
        logger.warning('Index out of range (%d of %d) for %r, path: %s', index, len(elems), entry.get('id'), tag_path)
        return None
    return elems[index]


def get_value(entry: Element, root: Element, dref_path: str, default: str, key: str = 'value') -> str:
    val: typing.Optional[str] = None
    elem: typing.Optional[Element] = entry
    last_type = ''
    tag_prev = ''
    for tag in dref_path.split('.'):
        if not elem:
            logger.warning('Failed to get: %s  in %s for %s', tag_prev, dref_path, entry.get('id'))
            return default
        # AreaArray[0].Radius
        if re.search(r'\[\d+\]', tag):
            search_result = re.search(r'\[.+\]', tag)
            if search_result is None:
                logger.warning('Failed to get: %s  in %s for %s', tag, dref_path, entry.get('id'))
                return default
            result = search_result.group()
            index = result.replace('[', '').replace(']', '')
            if elem:
                elem = get_array_elem(elem, root, tag.split('[')[0], int(index))
                last_type = 'indexed_arr'
        # KillResource[Minerals]
        elif '[' in tag:
            search_result = re.search(r'\[[a-zA-Z]+\]', tag)
            if search_result is None:
                logger.warning('Failed to get: %s  in %s for %s', tag, dref_path, entry.get('id'))
                return default
            result = search_result.group()
            index = result.replace('[', '').replace(']', '')
            tag = tag.split('[')[0]
            if elem:
                elem = elem.find(f'{tag}[@index="{index}"]')
                last_type = 'named_arr'
        # Modification.AttackSpeedMultiplier
        else:
            if elem:
                elem = elem.find(tag)
                last_type = 'simple'
        tag_prev = tag

    if elem is not None:
        val = elem.get(key)
    if val is None:
        if last_type == 'named_arr':
            val = get_default_array(tag, index)
        elif last_type == 'simple':
            if tag == 'DisplayEffect':
                val = entry.get('id')
            else:
                val = get_default(entry.tag, tag)
        if val is None:
            logger.warning('Failed to get: %s for %s', dref_path, entry.get('id'))
            return default
    return val


def get_entry(root: Element, entry_id: str) -> typing.Optional[Element]:
    return root.find(f'*[@id="{entry_id}"]')


def get_parent(entry: Element, root: Element) -> typing.Optional[Element]:
    parent = entry.get('parent')
    if parent:
        return get_entry(root, parent)
    return None


def apply_indexed_array(child: Element, template: Element, tag: str) -> None:
    """
    - If there is no attributes but 'value' then they just go in order (template's last, +1 etc)
    - 'index' attr means child overrides template's array at that index
    - 'removed' attr means array member at that index is simply deleted
    - tempplates don't have these attributes
    """
    t_elems = template.findall(f'{tag}')
    if not t_elems:
        return
    c_elems = child.findall(f'{tag}')
    overr_index: list[int] = []
    removed_index: list[int] = []
    for c_elem in c_elems:
        i = int(c_elem.get('index', '-1'))
        if i < 0:
            continue
        if i > len(t_elems) - 1:
            logger.warning(f'{c_elem.tag} index is out of range ({i})')
            continue
        del c_elem.attrib['index']
        if 'removed' in c_elem.attrib:
            child.remove(c_elem)
            removed_index.append(i)
        else:
            overr_index.append(i)
            apply_template(c_elem, t_elems[i])

    for i in reversed(removed_index):
        t_elems.pop(i)
    for i in range(len(t_elems)):
        if i in overr_index:
            continue
        t = t_elems[i]
        new_el = xml.etree.ElementTree.Element(t.tag, t.attrib)
        child.insert(i, new_el)
        apply_template(new_el, t)


def apply_named_array(child: Element, template_sub: Element) -> None:
    index = template_sub.get('index', '')
    c_sub = child.find(f'{template_sub.tag}[@index="{index}"]')
    if c_sub is None:
        child.append(template_sub)
    elif len(template_sub) > 0:
        apply_template(c_sub, template_sub)
    else:
        # child overrides simple element
        pass


def apply_template(child: Element, template: Element) -> None:
    handled_arrays: list[str] = []
    for t_sub in template.findall('*'):
        if t_sub.tag in handled_arrays:
            continue
        # technically this array works, but since we aren't currently reading from core.sc2mod,
        # and the fact we don't need it, its better to just skip to avoid error spam (due to 'On index=.. overrides)
        # where index is usually very high number, so we will keep getting index out of range
        if t_sub.tag == 'On':
            continue
        # if element doesn't exist and doesn't require array handling, just append
        if not elem_is_array(t_sub.tag) and not elem_has_subtag(child, t_sub.tag):
            child.append(t_sub)
            continue
        # element exists and is complex type (need to check for subelements recursively)
        if not elem_is_array(t_sub.tag) and len(t_sub) > 0:
            c_sub = child.find(t_sub.tag)
            if c_sub:
                apply_template(c_sub, t_sub)
            continue
        if elem_is_named_array(t_sub):
            apply_named_array(child, t_sub)
            continue
        # indexed array (we handle all p_sub tags in one go, otherwise it gets complicated)
        if elem_is_indexed_array(t_sub):
            handled_arrays.append(t_sub.tag)
            apply_indexed_array(child, template, t_sub.tag)


def find_templates_and_apply(root: Element) -> None:
    # please don't template to non defaults for 2 reasons:
    # 1) this function only loops through defaults
    # 2) in sc2 templating to non defaults causes weird behaviors sometimes
    templates = root.findall('*[@default="1"]')
    for t in templates:
        children = root.findall(f'*[@parent="{t.get("id")}"]')
        for c in children:
            apply_template(c, t)


def reformat_xml(root: Element) -> None:
    """
    Ensure no tags are "shortened" inside parent node's attribute. They should be in consistent form:
    <Modification>
        <AttackSpeedMultiplier value="2"/>
    </Modification>
    and not as:
    <Modification AttackSpeedMultiplier="2"/>
    """
    # "primitive" keys, the ones that point to the actual value
    exclude = ('value', 'id', 'index', 'parent', 'default', 'removed')
    for e in list(root.iter()):
        # few tags we don't want to change
        if e.tag in ('const', 'Catalog', 'Comment'):
            continue
        for key, val in list(e.attrib.items()):
            if key not in exclude:
                xml.etree.ElementTree.SubElement(e, key, {'value': val})
                e.attrib.pop(key)


def load_xml(file: pathlib.Path) -> Element:
    root = xml.etree.ElementTree.parse(file).getroot()
    reformat_xml(root)
    find_templates_and_apply(root)
    return root


def get_default(source_tag: str, tag: str) -> typing.Optional[str]:
    return DEFAULTS.get((source_tag, tag), None)


def get_default_array(tag: str, index: str) -> typing.Optional[str]:
    return DEFAULTS_ARRAY.get((tag, index), None)


def pretty_output_xml(root: Element, file: str) -> None:
    logger.addHandler(logging.FileHandler(file, mode='w'))
    xml_str = xml.etree.ElementTree.tostring(root, xml_declaration=True)
    dom = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='    ', encoding='utf-8').decode()
    dom = '\n'.join(line for line in dom.split('\n') if line.strip())
    logger.debug(dom)


def main() -> None:
    root = load_xml(pathlib.Path(__file__).parent.parent.resolve() / 'data/GameData/UnitData.xml')
    logger.setLevel(logging.DEBUG)
    pretty_output_xml(root, 'debug/log.xml')


if __name__ == '__main__':
    main()

DEFAULTS = {('CEffectDamage', 'Amount'): '0', ('CEffectDamage', 'Random'): '0', ('CEffectDamage', 'Fraction'): '1', ('CEffectDamage', 'Kind'): 'Melee',
            ('CWeaponLegacy', 'Range'): '5', ('CWeaponLegacy', 'Period'): '0.8332', ('CWeaponLegacy', 'DisplayAttackCount'): '1', ('CUnit', 'LifeMax'): '1',
            ('CUnit', 'ShieldsMax'): '0', ('CUnit', 'EnergyMax'): '0', ('CUnit', 'Food'): '0', ('CEffectDamage', 'Type'): 'None'}

DEFAULTS_ARRAY = {('CostResource', 'Vespene'): '0', ('CostResource', 'Minerals'): '0', ('CostResource', 'Terrazine'): '0', ('KillResource', 'Vespene'): '0',
                  ('KillResource', 'Minerals'): '0', ('KillResource', 'Terrazine'): '0', ('Options', 'Melee'): '0'}
