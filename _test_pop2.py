# -*- coding: utf-8 -*-
import sys, asyncio
sys.path.insert(0, r'e:\PY\all_tame_channel')
from Agent.children_agent.algorithm_lab_agent import AlgorithmLabAgent
agent = AlgorithmLabAgent()

async def main():
    state = agent.get_initial_state('stack', 5)
    print('Initial stack (5 nodes):')
    for n in state['nodes']:
        print('  %s: val=%s y=%s' % (n['id'], n['value'], n['position_y']))
    print('  top=%s' % state['pointers']['top'])

    # 模拟前端的平移：假设平移后坐标变了
    # 前端 addOperationToHistory 会做平移和缩放
    # 模拟第一次 pop
    r1 = await agent.execute_operation_async('stack', 'pop', {}, state)
    fs1 = r1['final_state']
    print('\nAfter 1st pop (backend result):')
    for n in fs1['nodes']:
        print('  %s: val=%s y=%s' % (n['id'], n['value'], n['position_y']))
    print('  top=%s' % fs1['pointers'].get('top'))
    print('  steps:')
    for s in r1['steps']:
        print('    step %s: line=%s desc=%s highlights=%s' % (s['step_id'], s['code_line'], s['description'], s.get('highlight_nodes', [])))

    # 模拟前端平移后的状态（坐标改变但 ID 不变）
    # 假设前端平移后 y 坐标都加了 100
    shifted_state = {
        'nodes': [{'id': n['id'], 'value': n['value'], 'position_x': n['position_x'], 'position_y': n['position_y'] + 100} for n in fs1['nodes']],
        'edges': fs1.get('edges', []),
        'pointers': fs1['pointers']
    }
    print('\nSimulated frontend state after shift:')
    for n in shifted_state['nodes']:
        print('  %s: val=%s y=%s' % (n['id'], n['value'], n['position_y']))
    print('  top=%s' % shifted_state['pointers'].get('top'))

    # 第二次 pop（用平移后的状态）
    r2 = await agent.execute_operation_async('stack', 'pop', {}, shifted_state)
    fs2 = r2['final_state']
    print('\nAfter 2nd pop (with shifted coords):')
    for n in fs2['nodes']:
        print('  %s: val=%s y=%s' % (n['id'], n['value'], n['position_y']))
    print('  top=%s' % fs2['pointers'].get('top'))
    print('  steps:')
    for s in r2['steps']:
        print('    step %s: line=%s desc=%s highlights=%s' % (s['step_id'], s['code_line'], s['description'], s.get('highlight_nodes', [])))

asyncio.run(main())
