# -*- coding: utf-8 -*-
"""Utilities to convert Python objects into dzn format and back."""
import re


class MiniZincSerializationError(RuntimeError):
    """
        Exception for errors encountered while serializing some Python object
        into dzn format.
    """

    def __init__(self, key, val):
        """
        Instantiate a new MiniZincSerializationError.
        :param key: The name of the variable that was impossible to serialize
        :param val: The value that was impossible to serialize
        """
        self.key = key
        self.val = val
        self.msg = 'Unsupported serialization for variable {} with value:\n{}'
        super().__init__(self.msg.format(self.key, self.val))


""" PYTHON TO DZN """


def _is_int(obj):
    return isinstance(obj, int)


def _is_value(obj):
    return isinstance(obj, (str, int, float))


def _is_set(obj):
    return isinstance(obj, set) and all(map(_is_value, obj))


def _is_elem(obj):
    return _is_value(obj) or _is_set(obj)


def _is_list(obj):
    return isinstance(obj, list)


def _is_dict(obj):
    return isinstance(obj, dict)


def _is_array_type(obj):
    return isinstance(obj, (list, dict))


def _list_index_set(obj):
    return 1, len(obj)


def _dict_index_set(obj):
    min_val = min(obj.keys())
    max_val = max(obj.keys())
    return min_val, max_val


def _is_contiguous(obj):
    if all(map(_is_int, obj)):
        min_val, max_val = min(obj), max(obj)
        return all([v in obj for v in range(min_val, max_val + 1)])
    return False


def _index_set(obj):
    if _is_list(obj) and len(obj) > 0:
        if all(map(_is_elem, obj)):
            return _list_index_set(obj),
        elif all(map(_is_array_type, obj)):
            idx_sets = list(map(_index_set, obj))
            if idx_sets[1:] == idx_sets[:-1]:
                return (_list_index_set(obj),) + idx_sets[0]
    elif _is_dict(obj) and len(obj) > 0 and _is_contiguous(obj.keys()):
        if all(map(_is_elem, obj.values())):
            return _dict_index_set(obj),
        elif all(map(_is_array_type, obj.values())):
            idx_sets = list(map(_index_set, obj.values()))
            if idx_sets[1:] == idx_sets[:-1]:
                return (_dict_index_set(obj),) + idx_sets[0]
    raise RuntimeError('The object is not a proper array: {}'.format(obj))


def _flatten_array(arr, lvl):
    if lvl == 1:
        return arr
    flat_arr = []
    for sub_arr in arr:
        flat_arr += _flatten_array(sub_arr, lvl - 1)
    return flat_arr


def _dzn_var(name, val):
    return '{} = {};'.format(name, val)


def _dzn_set(vals):
    if _is_contiguous(vals):
        min_val, max_val = _dict_index_set(vals)
        return '{}..{}'.format(min_val, max_val)  # contiguous set
    return '{{ {} }}'.format(', '.join(map(str, vals)))


def _dzn_array_nd(arr):
    idx_set = _index_set(arr)
    dim = len(idx_set)
    if dim > 6:  # max 6-dimensional array in dzn language
        raise MiniZincParsingError(arr)
    flat_arr = _flatten_array(arr, dim)
    dzn_arr = 'array{}d({}, {})'
    idx_set_str = ', '.join(['{}..{}'.format(*s) for s in idx_set])
    arr_str = '[' + ', '.join(map(str, flat_arr)) + ']'
    return dzn_arr.format(dim, idx_set_str, arr_str)


def dzn(objs, fout=None):
    """
    Parse the objects in input and produces a list of strings encoding them
    into the dzn format. Optionally, the produced dzn is written in a given
    file.

    Supported types of objects include: str, int, float, set, list or dict.
    List and dict are serialized into dzn (multi-dimensional) arrays. The
    key-set of a dict is used as index-set of dzn arrays. The index-set of a
    list is implicitly set to 1..len(list).

    :param dict objs: A dictionary containing key-value pairs where keys are
                      the names of the variables
    :param str fout: Path to the output file, if None no output file is written
    :return: List of strings containing the dzn encoded objects
    :rtype: list
    """

    vals = []
    for key, val in objs.items():
        if _is_value(val):
            vals.append(_dzn_var(key, val))
        elif _is_set(val):
            s = _dzn_set(val)
            vals.append(_dzn_var(key, s))
        elif _is_array_type(val):
            arr = _dzn_array_nd(val)
            vals.append(_dzn_var(key, arr))
        else:
            raise MiniZincSerializationError(key, val)

    if fout:
        with open(fout, 'w') as f:
            for val in vals:
                f.write(val + '\n')

    return vals


""" DZN TO PYTHON """


class MiniZincParsingError(RuntimeError):
    """
        Exception for errors encountered while parsing the output of the
        FlatZinc solution output stream.
    """

    def __init__(self, val):
        """
        Instantiate a new MiniZincParsingError.
        :param val: The value that was impossible to parse
        """
        self.val = val
        self.msg = 'Unsupported parsing for value: {}'.format(self.val)
        super().__init__(self.msg)


# For now support only numerical values and numeric arrays and sets

# integer pattern
_int_p = re.compile('^[+\-]?\d+$')

# float pattern
_float_p = re.compile('^[+\-]?\d*\.\d+(?:[eE][+\-]?\d+)?$')

# continuous integer set pattern
_cont_int_set_p = re.compile('^([+\-]?\d+)\.\.([+\-]?\d+)$')

# integer set pattern
_int_set_p = re.compile('^(\{(?P<vals>[\d ,+\-]*)\})$')

# matches any of the previous
_val_p = re.compile(('(?:\{(?:[\d ,+\-]+)\}|(?:[+\-]?\d+)\.\.(?:[+\-]?\d+)|['
                     '+\-]?\d*\.\d+(?:[eE][+\-]?\d+)?|[+\-]?\d+)'))

# multi-dimensional array pattern
_array_p = re.compile(('^(?:array(?P<dim>\d)d\s*\((?P<indices>(?:\s*['
                       '\d\.+\-]+(\s*,\s*)?)+)\s*,\s*)?\[(?P<vals>[\w \.,'
                       '+\-\\\/\*^|\(\)\{\}]+)\]\)?$'))

# variable pattern
_var_p = re.compile(('^\s*(?P<var>[\w]+)\s*=\s*(?P<val>[\w \.,+\-\\\/\*^|\('
                     '\)\[\]\{\}]+);?$'))


def dict2array(d):
    """
    Transform an indexed dictionary (such as those returned by the parse_dzn
    function when parsing arrays) into an multi-dimensional array.

    :param dict d: The indexed dictionary to convert
    :return: A multi-dimensional array
    :rtype: list
    """
    arr = []
    idx_set = _dict_index_set(d)
    for idx in idx_set:
        v = d[idx]
        if isinstance(v, dict):
            v = dict2array(v)
        arr.append(v)
    return arr


def _parse_array(indices, vals):
    # Recursive parsing of multi-dimensional arrays returned by the solns2out
    # utility of the type: array2d(2..4, 1..3, [1, 2, 3, 4, 5, 6, 7, 8, 9])
    idx_set = indices[0]
    if len(indices) == 1:
        arr = {i: _parse_val(vals.pop(0)) for i in idx_set}
    else:
        arr = {i: _parse_array(indices[1:], vals) for i in idx_set}
    return arr


def _parse_indices(st):
    # Parse indices inside multi-dimensional arrays
    ss = st.strip().split(',')
    indices = []
    for s in ss:
        s = s.strip()
        cont_int_set_m = _cont_int_set_p.match(s)
        if cont_int_set_m:
            v1 = int(cont_int_set_m.group(1))
            v2 = int(cont_int_set_m.group(2))
            indices.append(range(v1, v2 + 1))
        else:
            raise MiniZincParsingError(s)
    return indices


def _parse_set(vals):
    # Parse sets of integers of the type: {41, 2, 53, 12, 8}
    p_s = set()
    for val in vals:
        p_val = val.strip()
        if _int_p.match(p_val):
            p_val = int(p_val)
            p_s.add(p_val)
        else:
            raise MiniZincParsingError(p_val)
    return p_s


def _parse_val(val):
    # integer value
    if _int_p.match(val):
        return int(val)

    # float value
    if _float_p.match(val):
        return float(val)

    # continuous integer set
    cont_int_set_m = _cont_int_set_p.match(val)
    if cont_int_set_m:
        v1 = int(cont_int_set_m.group(1))
        v2 = int(cont_int_set_m.group(2))
        return set(range(v1, v2 + 1))

    # integer set
    set_m = _int_set_p.match(val)
    if set_m:
        vals = set_m.group('vals')
        if vals:
            return _parse_set(vals.split(','))
        return set()
    return None


def parse_dzn(lines):
    """
    Parse the one solution from the output stream of the solns2out utility.

    :param [str] lines: The stream of lines from a given solution
    :return: A dictionary containing the variable assignments parsed from
             the input stream
    :rtype: dict
    """
    parsed_vars = {}
    for l in lines:
        l = l.strip()
        var_m = _var_p.match(l)
        if var_m:
            var = var_m.group('var')
            val = var_m.group('val')
            p_val = _parse_val(val)
            if p_val is not None:
                parsed_vars[var] = p_val
                continue

            array_m = _array_p.match(val)
            if array_m:
                vals = array_m.group('vals')
                vals = _val_p.findall(vals)
                dim = array_m.group('dim')
                if dim:  # explicit dimensions
                    dim = int(dim)
                    indices = _parse_indices(array_m.group('indices'))
                    assert len(indices) == dim
                    p_val = _parse_array(indices, vals)
                else:  # assuming 1d array based on 0
                    p_val = _parse_array([range(len(vals))], vals)
                parsed_vars[var] = p_val
                continue
        raise MiniZincParsingError(l)
    return parsed_vars