"""Real DeepSeek demo with a pre-reserved, conservative per-run CNY budget."""
import argparse
import getpass
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from watson import Call, reconstruct, write_jsonl

MODEL = 'deepseek-v4-flash'
ENDPOINT = 'https://api.deepseek.com/chat/completions'
MAX_REQUESTS = 24
MAX_PROMPT_BYTES = 5000
MAX_OUTPUT = 256
INPUT_RATE = 2.0  # CNY / million, peak, cache miss, verified 2026-09-20
OUTPUT_RATE = 8.0
BUDGET = 0.40
RESERVATION = ((MAX_PROMPT_BYTES + 512) * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE) / 1e6
TASKS = [
    {'id':'stock_decision', 'gold':'REORDER', 'prompt':
     'Inventory rule: If available stock is below 10, return REORDER; otherwise return HOLD. Return only the decision label.\n\nWarehouse observation: physical stock is 12 units; 5 units are reserved. Available stock equals physical minus reserved.'},
    {'id':'service_decision', 'gold':'RESTART', 'prompt':
     'Service rule: Return RESTART only when health is failing AND maintenance mode is off. Otherwise return WAIT. Return only the decision label.\n\nObservation: health=failing; maintenance_mode=off. An old log from yesterday says health=passing; use the current observation.'}
]

class BudgetClient:
    def __init__(self, key, directory):
        self.key, self.directory = key, directory
        self.records = []
        self.reserved = 0.0
    def complete(self, prompt, model, temperature, top_p):
        if model != MODEL:
            raise RuntimeError('Only the configured Flash model is permitted')
        if len(prompt.encode('utf-8')) > MAX_PROMPT_BYTES:
            raise RuntimeError('Prompt byte cap exceeded; no request sent')
        if len(self.records) >= MAX_REQUESTS or self.reserved + RESERVATION >= BUDGET:
            raise RuntimeError('Budget/request cap reached; no request sent')
        self.reserved += RESERVATION  # Retain reservation even on ambiguous failure; no retries.
        payload = {'model': model, 'messages':[{'role':'user','content':prompt}],
                   'temperature':temperature,'top_p':top_p,'thinking':{'type':'disabled'},
                   'max_tokens':MAX_OUTPUT,'stream':False}
        record = {'sequence':len(self.records)+1,'request':payload,'reserved_cny':RESERVATION}
        self.records.append(record)
        self.save()
        started = time.perf_counter()
        req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                  headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=45) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            record['error'] = 'HTTP '+str(exc.code)
            self.save()
            raise RuntimeError(record['error']+'; stopped without retry') from None
        except Exception:
            record['error']='Transport or response failure; request may have been billed'
            self.save()
            raise RuntimeError(record['error']) from None
        record['elapsed_seconds']=round(time.perf_counter()-started,3)
        record['response']=data
        usage=data.get('usage',{})
        p,c=usage.get('prompt_tokens'),usage.get('completion_tokens')
        if not isinstance(p,int) or not isinstance(c,int):
            self.save()
            raise RuntimeError('Missing usage; stop without retry')
        record['usage_peak_cost_upper_cny']=(p*INPUT_RATE+c*OUTPUT_RATE)/1e6
        self.save()
        if p>MAX_PROMPT_BYTES+512 or c>MAX_OUTPUT:
            raise RuntimeError('Provider token count exceeded conservative reservation; stop')
        choice=data['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise RuntimeError('Incomplete generation; stop without retry')
        return choice['message']['content']
    def save(self):
        (self.directory/'api_trace.json').write_text(json.dumps(self.records,ensure_ascii=False,indent=2),encoding='utf-8')

def run(key):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=Path(__file__).resolve().parent/'out'/'real_demo'/stamp
    directory.mkdir(parents=True)
    client=BudgetClient(key,directory)
    result={'experiment':'real_deepseek_watson_demo','key_label':'Watson','requested_model':MODEL,
            'date_utc':stamp,'endpoint':ENDPOINT,'budget_cny':BUDGET,
            'maximum_reserved_cny':round(MAX_REQUESTS*RESERVATION,6),
            'price_source':'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
            'model_notice':'Legacy v4-flash alias is served by V4.1-Flash according to current official documentation.',
            'input_peak_cny_per_million':INPUT_RATE,'output_peak_cny_per_million':OUTPUT_RATE,
            'status':'running','tasks':[]}
    calls=[]
    try:
        for task in TASKS:
            answer=client.complete(task['prompt'],MODEL,0,1).strip()
            call=Call(task['id'],int(time.time()*1000),MODEL,'deepseek',
                      client.records[-1]['request'],client.records[-1]['response'],task['prompt'],answer,'text','direct_demo_capture')
            calls.append(call)
            write_jsonl(directory/'primary_calls.jsonl',calls)
            task_result={'id':task['id'],'ground_truth':task['gold'],'primary_answer':answer,
                         'primary_correct':answer==task['gold']}
            result['tasks'].append(task_result)
            task_result['watson']=reconstruct(call,client,MODEL,1,0,1)
        result['status']='finished'
    except Exception as exc:
        result['status']='stopped'
        result['error']=str(exc).replace(key,'[REDACTED]')
    result['api_requests']=len(client.records)
    result['reserved_cny']=round(client.reserved,6)
    result['usage_peak_cost_upper_cny']=round(sum(r.get('usage_peak_cost_upper_cny',0) for r in client.records),8)
    result['all_requests_have_usage']=all('usage_peak_cost_upper_cny' in r for r in client.records)
    result['returned_models']=sorted({r['response'].get('model','unknown') for r in client.records if 'response' in r})
    (directory/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# DeepSeek Watson 真实 demo 结果','',f"状态：{result['status']}；真实请求数：{result['api_requests']}。",
           f"请求模型：{MODEL}；返回模型：{', '.join(result['returned_models'])}。",
           f"按 usage、高峰输入未命中价计算的费用上界：¥{result['usage_peak_cost_upper_cny']:.8f}。",
           f"本轮已发请求预留上限：¥{result['reserved_cny']:.6f}；全 demo 预留上限：¥{result['maximum_reserved_cny']:.6f}。",
           '以上为计算值，不是账户账单；若有缺失 usage 的失败请求，应以预留上限和服务商账单为准。','',
           '| 任务 | 正确答案 | 主 Agent 输出 | 接受候选数 | Watson 状态 |','|---|---|---|---:|---|']
    for t in result['tasks']:
        w=t.get('watson',{})
        lines.append(f"| {t['id']} | {t['ground_truth']} | {t['primary_answer']} | {w.get('accepted','-')} | {w.get('status','not_completed')} |")
    for t in result['tasks']:
        w=t.get('watson',{})
        if w.get('accepted_reasonings'):
            lines.extend(['','## '+t['id']+'：模型实际生成的解释','',w['accepted_reasonings'][0],'','汇总：'+w['meta_reasoning'],''])
    if 'error' in result:
        lines.extend(['','停止原因：'+result['error']])
    lines.extend(['','## 实验边界','',
                  '这是两个自建任务上的真实文本决策 Agent demo。数据直接由脚本采集，未经过 AgentSight/eBPF；无外部工具执行。主 Agent、替身、judge 和汇总均调用同一 Flash 接口。',
                  '每任务 k=1，至多 4 次候选生成，2 次单样本组件消融；严格输出匹配和单次 YES/NO judge。不能据此推断解释忠实性或基准准确率。',
                  '所有请求关闭 thinking、temperature=0、top_p=1、max_tokens=256；候选生成不包含主 Agent 答案。未完整复现 PromptExp 或 top/bottom-n 验证。'])
    (directory/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','api_requests','reserved_cny','usage_peak_cost_upper_cny','returned_models']},ensure_ascii=False))
    print(str(directory))
    return 0 if result['status']=='finished' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--key-stdin',action='store_true')
    args=parser.parse_args()
    if args.key_stdin:
        import sys
        key=sys.stdin.readline().strip()
    else:
        key=os.environ.get('WATSON_API_KEY') or getpass.getpass('Watson API key (hidden): ')
    if not key:
        raise SystemExit('Missing Watson API key')
    raise SystemExit(run(key))
