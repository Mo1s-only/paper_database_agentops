"""Deterministic control-flow experiments; no real model performance claims."""
import hashlib
import json
from pathlib import Path
from watson import Call, extract_calls, reconstruct, normalize_response, matches_expected

class ScriptedClient:
    def __init__(self, mode):
        self.mode = mode
        self.requests = 0
        self.generations = 0
    def complete(self, prompt, model, temperature, top_p):
        self.requests += 1
        if prompt.startswith('Return only YES or NO'):
            return 'NO' if self.mode == 'judge_reject' else 'YES'
        if prompt.startswith('Summarize the following'):
            return 'Synthetic fixture summary; not evidence about model reasoning.'
        assert 'TARGET_SENTINEL_739' not in prompt, 'Answer leaked into generation'
        self.generations += 1
        if 'Choose the stored symbol' not in prompt:
            return 'Missing task.\nFINAL: unknown'
        if self.mode == 'wrong' or (self.mode == 'alternating' and self.generations % 2 == 0):
            return 'Synthetic wrong candidate.\nFINAL: other'
        return 'Synthetic matching candidate.\nFINAL: TARGET_SENTINEL_739'

def run():
    output = Path(__file__).resolve().parent / 'out' / 'offline_experiment'
    output.mkdir(parents=True, exist_ok=True)
    call = Call('synthetic', 0, 'fixture', 'offline', {}, {},
                '[system]\nFollow the task.\n\n[user]\nChoose the stored symbol.',
                'TARGET_SENTINEL_739', 'text', 'synthetic_fixture')
    results = []
    for mode in ['accept', 'wrong', 'judge_reject', 'alternating']:
        for k in [1, 3, 5, 10]:
            client = ScriptedClient(mode)
            result = reconstruct(call, client, 'fixture', k, 0, 1)
            assert result['api_requests'] == client.requests
            assert result['attempts'] <= 4*k
            assert result['accepted'] == (0 if mode in ['wrong','judge_reject'] else k)
            assert result['status'] == ('insufficient_candidates' if mode in ['wrong','judge_reject'] else 'complete')
            results.append({'mode': mode, 'k': k, **result})
    assert not matches_expected('TARGET_SENTINEL_739', call.output)
    for response in [
        {'choices':[{'message':{'content':'text','tool_calls':[{'id':'t'}]}}]},
        {'content':[{'type':'text','text':'text'},{'type':'tool_use','id':'t'}]}
    ]:
        assert normalize_response(response)[1] != 'text'
    skipped_client = ScriptedClient('accept')
    orphan = Call('orphan',0,None,None,{}, {}, '', 'answer','text')
    assert reconstruct(orphan, skipped_client, 'fixture',1,0,1)['status'] == 'skipped'
    assert skipped_client.requests == 0
    db = Path(__file__).resolve().parent.parent / 'agentsight/test/out/session.db'
    audit = {'exists': db.exists()}
    if db.exists():
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        calls = extract_calls(db)
        audit.update(total=len(calls), with_prompt=sum(bool(c.prompt) for c in calls),
                     text_eligible=sum(bool(c.prompt and c.output and c.completion_kind=='text') for c in calls),
                     missing_request=sum(not bool(c.request) for c in calls))
        audit['database_unchanged'] = before == hashlib.sha256(db.read_bytes()).hexdigest()
        assert audit['database_unchanged']
    artifact = {'experiment_type':'synthetic_offline_control_flow',
                'real_model_requests':0, 'audit':audit, 'runs': results}
    (output/'results.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['# Watson 离线实验结果', '',
             '本轮是确定性假客户端的控制流与故障注入实验，不能作为真实模型准确率、解释忠实性或论文效果复现的证据。', '',
             '| 场景 | k | 尝试数 | 匹配数 | 接受数 | 请求总数 | 状态 |',
             '|---|---:|---:|---:|---:|---:|---|']
    for r in results:
        lines.append(f"| {r['mode']} | {r['k']} | {r['attempts']} | {r['matched']} | {r['accepted']} | {r['api_requests']} | {r['status']} |")
    lines += ['', '## 数据准入审计', '', '```json', json.dumps(audit,ensure_ascii=False,indent=2), '```', '',
              '## 本轮修正与边界', '',
              '- 对照 Watson.pdf 第 4 页 RepCoT 描述：候选生成不再看到目标输出；目标仅用于生成后的匹配筛选。',
              '- 消融生成同样不再包含目标输出；无 FINAL 标记的结果不算匹配。',
              '- 拒绝混合文本和工具调用记录；未配对记录跳过且不调用模型。',
              '- 保存候选、匹配结果、judge verdict、请求数及包含消融在内的耗时；采样耗尽标记 insufficient_candidates。',
              '- 当前使用严格文本匹配，原文使用语义等价 judge；单次离散消融也不等价于 PromptExp 概率归因。',
              '- 消息角色被展平，镜像标记 approximate；尚未实现原文 top/bottom-n judge、token 计费及真实基准。',
              '- 未检测到 WATSON 配置环境变量，本轮没有调用外部模型。',
              '- 真实实验需先取得可配对的文本调用与模型端点、模型名及密钥，再开展 5 条试运行。']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'matrix_runs':len(results),'audit':audit,'output':str(output)},ensure_ascii=False))

if __name__ == '__main__':
    run()
