"""Validate the JSON Schema subset used here; report shapes allow optional upstream fields."""
import json
import math
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'


def validate(value, schema, path='$', root=None):
    root = schema if root is None else root
    if '$ref' in schema:
        prefix = '#/$defs/'
        ref = schema['$ref']
        if not ref.startswith(prefix):
            raise ValueError('只支援本地 $defs schema，不讀取外部內容。')
        return validate(value, root['$defs'][ref[len(prefix):]], path, root)
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    matches = {'null':value is None,'object':isinstance(value,dict),'array':isinstance(value,list),
               'string':isinstance(value,str),'boolean':type(value) is bool,
               'integer':type(value) is int,'number':type(value) in (int,float)}
    if types and not any(matches.get(kind,False) for kind in types):
        raise ValueError(f'{path}: 型別不符合 {types}')
    if type(value) in (int,float) and not math.isfinite(value):
        raise ValueError(f'{path}: 數值必須有限')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{path}: 不在允許值中')
    if isinstance(value,dict):
        for key in schema.get('required',[]):
            if key not in value:
                raise ValueError(f'{path}: 缺少 {key}')
        properties=schema.get('properties',{})
        for key,item in value.items():
            if key in properties:
                validate(item,properties[key],path+'.'+key,root)
            elif schema.get('additionalProperties') is False:
                raise ValueError(f'{path}: 未知欄位 {key}')
            elif isinstance(schema.get('additionalProperties'),dict):
                validate(item,schema['additionalProperties'],path+'.'+key,root)
    elif isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',float('inf')):
            raise ValueError(f'{path}: 陣列長度不符')
        for index,item in enumerate(value):
            validate(item,schema.get('items',{}),f'{path}[{index}]',root)
    elif isinstance(value,str) and len(value)<schema.get('minLength',0):
        raise ValueError(f'{path}: 字串過短')
    elif type(value) in (int,float):
        if 'minimum' in schema and value<schema['minimum']:
            raise ValueError(f'{path}: 低於最小值')
        if 'exclusiveMinimum' in schema and value<=schema['exclusiveMinimum']:
            raise ValueError(f'{path}: 必須大於最小值')


def validate_rules(rules):
    schema=json.loads((SCHEMAS/'validation-rules.schema.json').read_text(encoding='utf-8'))
    validate(rules,schema)
    return rules


def validate_report(report,kind):
    if kind not in {'erc','drc'}:
        raise ValueError('未知報告種類。')
    schema=json.loads((SCHEMAS/f'kicad-{kind}-report.schema.json').read_text(encoding='utf-8'))
    validate(report,schema)
    return report
