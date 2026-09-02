from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage, OpenAIResponsesLLMClient
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.pipelines.multi_agent_pipeline import MultiAgentPipeline
from ai.app.orchestration.pipelines.single_rag_pipeline import SingleRAGPipeline
from ai.app.retrieval import RetrievedChunk
from ai.app.schemas import TraceContext

OUT = ROOT / "ai/experiment_results/e05/qualitative"
ENV_PATH = ROOT / "backend/.env"


def load_backend_env() -> None:
    """Load backend/.env without printing secrets."""
    if not ENV_PATH.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        # Minimal safe fallback: parse KEY=VALUE lines without executing the file.
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"'", '"'}
            ):
                value = value[1:-1]
            os.environ.setdefault(key, value)
    else:
        load_dotenv(ENV_PATH, override=False)


load_backend_env()
EXPECTED_SHA = "68666b88fcf33273906710f23a8d17f7f1faa07f"
MODEL = "WPUJAC104DWH"
INQUIRY = "018f2f9b-7c30-7981-b541-1a987c88b701"
CORRELATION = "018f2f9b-7c30-7981-b541-1a987c88e701"
NORMAL = "어제부터 냉수 버튼을 누르면 물이 졸졸 나옵니다. 전원을 껐다 켰어요."
GAP = "정수기 상태가 이상합니다."
DANGER = "정수기 밑 바닥에 물이 새서 누수가 심합니다."
EVIDENCE = "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인하고, 필요한 기본 점검 후에도 증상이 지속되면 전문 상담 및 점검을 요청합니다."

def git_sha():
    try:
        return subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,encoding="utf-8").strip()
    except Exception:
        return "UNKNOWN"

class EvidenceSearch:
    def __init__(self): self.calls=0
    def search(self,*args,**kwargs):
        self.calls+=1
        return [RetrievedChunk(
            chunk_id="E05Q-JAC104-COLD-001", document_title="WPU-JAC104D 사용설명서",
            document_version="REV.00", page=37, page_refs=[37], manual_model=MODEL,
            model_code=MODEL, product_generation="D", content=EVIDENCE,
            similarity_score=0.95, verification_status="official_verified",
            allowed_use=True, runtime_eligible=True, topic_code="symptom_low_flow")]

class EmptySearch:
    def __init__(self): self.calls=0
    def search(self,*args,**kwargs):
        self.calls+=1
        return []

class FailSearch:
    def __init__(self): self.calls=0
    def search(self,*args,**kwargs):
        self.calls+=1
        raise AssertionError("Danger 경로에서는 Retrieval이 호출되면 안 됩니다.")

class OfflineLLM:
    def __init__(self): self.calls=0
    def generate_guidance(self,request,*,timeout_seconds):
        self.calls+=1
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                selected_evidence_index=0,
                next_actions=[request.allowed_next_actions[0]] if request.allowed_next_actions else ["전문 상담을 요청하세요."]),
            model_name="offline-contract-client",
            usage=LLMUsage(input_tokens=0,output_tokens=0,total_tokens=0), latency_ms=0.0)

def llm_client(offline, model):
    if offline:
        return OfflineLLM(), "OFFLINE_CONTRACT_CLIENT"
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다. 실제 답변은 키를 설정하고 실행하세요. API 없이 구조만 확인하려면 --offline.")
    return OpenAIResponsesLLMClient(api_key=key,model_name=model,temperature=0.0,max_output_tokens=500), model

def ctx(case_id,text,selected=None):
    suffix={"NORMAL_EVIDENCE":"1","EVIDENCE_GAP_FEEDBACK":"2","DANGER_LEAK":"3"}[case_id]
    return PipelineContext(
        trace_context=TraceContext(
            inquiry_id=INQUIRY[:-1]+suffix, correlation_id=CORRELATION[:-1]+suffix,
            ai_request_id=f"e05q-{case_id.lower()}", state_version=1),
        raw_symptom=text, model_code=MODEL, selected_symptoms=selected or [])

def val(x): return getattr(x,"value",x)

def dump(x):
    if x is None: return None
    return x.model_dump(mode="json") if hasattr(x,"model_dump") else x

def questions(items):
    out=[]
    for x in items or []:
        d=dump(x)
        if isinstance(d,dict):
            out.append(str(d.get("question_text") or d.get("question") or d.get("text") or d.get("prompt") or json.dumps(d,ensure_ascii=False)))
        else: out.append(str(d))
    return out

def evidences(items):
    out=[]
    for x in items or []:
        d=dump(x)
        if isinstance(d,dict):
            out.append({k:d.get(k) for k in ("chunk_id","document_title","page","summary")})
        else: out.append({"raw":str(d)})
    return out

def extract(result,runtime,search_calls,elapsed):
    r=result.to_analysis_result(); g=r.usage_guidance; m=result.multi_agent_metadata
    handoffs=[]
    if m is not None:
        for h in m.handoffs:
            d=h.model_dump(mode="json")
            handoffs.append({"from":d.get("from_agent"),"to":d.get("to_agent"),"reason":d.get("reason_code"),"hop":d.get("hop_count")})
    return {
        "runtime":runtime,"status":val(r.status),"routing_disposition":val(result.routing_disposition),
        "failure_stage":val(r.failure_stage),"fallback_reason_code":val(r.fallback_reason_code),
        "risk_level":val(r.safety_assessment.risk_level),"requires_consultation":r.safety_assessment.requires_consultation,
        "retrieval_outcome":val(result.context.retrieval_outcome),
        "awaiting_customer_input":bool(result.context.awaiting_customer_input),
        "guidance_status":val(g.guidance_status),"message":g.message,
        "restricted_functions":list(g.restricted_functions),"next_actions":list(g.next_actions),
        "followup_questions":questions(r.followup_questions),"evidence":evidences(r.evidence_references),
        "search_calls":search_calls,"model_name":result.context.model_metadata.model_name,
        "tokens_used":result.context.model_metadata.tokens_used,"llm_latency_ms":result.context.model_metadata.latency_ms,
        "pipeline_elapsed_ms":round(elapsed,3),"multi_handoffs":handoffs}

def run(runtime,case_id,text,search,llm,selected=None):
    p=(SingleRAGPipeline if runtime=="single_rag" else MultiAgentPipeline)(search_service=search,llm_client=llm)
    started=time.perf_counter(); result=p.run(ctx(case_id,text,selected)); elapsed=(time.perf_counter()-started)*1000
    return extract(result,runtime,getattr(search,"calls",0),elapsed)

def render_side(label,row):
    lines=[f"### {label}","",f"- status: `{row['status']}`",f"- guidance: `{row['guidance_status']}`",
           f"- retrieval: `{row['retrieval_outcome']}`",f"- awaiting_customer_input: `{row['awaiting_customer_input']}`","",
           "**고객에게 보이는 안내**","",f"> {row['message']}",""]
    if row["next_actions"]: lines += ["**다음 행동**"]+[f"- {x}" for x in row["next_actions"]]+[""]
    if row["followup_questions"]: lines += ["**추가 질문**"]+[f"- {x}" for x in row["followup_questions"]]+[""]
    if row["multi_handoffs"]:
        lines += ["**Multi-Agent Handoff**"]+[f"- `{h['from']}` → `{h['to']}` : `{h['reason']}`" for h in row["multi_handoffs"]]+[""]
    return lines

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--offline",action="store_true")
    ap.add_argument("--model",default="gpt-4.1-mini-2025-04-14")
    a=ap.parse_args()
    llm,provider=llm_client(a.offline,a.model); sha=git_sha()
    cases=[]
    cases.append({"case_id":"NORMAL_EVIDENCE","purpose":"정상 경로 고객-facing 결과 비교","customer_input":NORMAL,
        "single_rag":run("single_rag","NORMAL_EVIDENCE",NORMAL,EvidenceSearch(),llm),
        "multi_agent":run("multi_agent","NORMAL_EVIDENCE",NORMAL,EvidenceSearch(),llm)})
    cases.append({"case_id":"EVIDENCE_GAP_FEEDBACK","purpose":"검색 실패 후 추가 문진 복구를 실제 문구로 확인","customer_input":GAP,
        "single_rag":run("single_rag","EVIDENCE_GAP_FEEDBACK",GAP,EmptySearch(),llm),
        "multi_agent":run("multi_agent","EVIDENCE_GAP_FEEDBACK",GAP,EmptySearch(),llm)})
    cases.append({"case_id":"DANGER_LEAK","purpose":"Danger에서 기존 Safety Contract 비열화 여부","customer_input":DANGER,
        "single_rag":run("single_rag","DANGER_LEAK",DANGER,FailSearch(),llm,["누수"]),
        "multi_agent":run("multi_agent","DANGER_LEAK",DANGER,FailSearch(),llm,["누수"])})
    gap=cases[1]
    conclusions={
        "gap_single_awaiting_customer_input":gap["single_rag"]["awaiting_customer_input"],
        "gap_multi_awaiting_customer_input":gap["multi_agent"]["awaiting_customer_input"],
        "gap_multi_followup_count":len(gap["multi_agent"]["followup_questions"]),
        "gap_multi_more_information_handoff":any(h.get("reason")=="MORE_INFORMATION_REQUIRED" for h in gap["multi_agent"]["multi_handoffs"]),
        "danger_single_search_calls":cases[2]["single_rag"]["search_calls"],
        "danger_multi_search_calls":cases[2]["multi_agent"]["search_calls"]}
    payload={"status":"E05_QUALITATIVE_COMPLETE","result_label":"QUALITATIVE_PRESENTATION_EVIDENCE",
             "git_sha":sha,"matches_original_e05_sha":sha==EXPECTED_SHA,"provider":provider,
             "note":"E05 정량 실험을 대체하지 않는 발표용 정성 사례. 정상 Evidence의 LLM 출력은 별도 API 호출이라 문구 자체의 완전 동일성을 평가하지 않는다.",
             "cases":cases,"conclusions":conclusions}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# E05-Q — Single RAG vs Multi-Agent 실제 응답 비교","",f"- Git SHA: `{sha}`",f"- Provider: `{provider}`",
        f"- Original E05 SHA 일치: `{sha==EXPECTED_SHA}`","","> E05 정량 실험을 대체하지 않는 발표용 Qualitative Evidence입니다.",""]
    for c in cases:
        md += [f"## {c['case_id']}","",f"**목적:** {c['purpose']}","",f"**고객 입력:** “{c['customer_input']}”",""]
        md += render_side("Single RAG",c["single_rag"])+render_side("Multi-Agent",c["multi_agent"])+["---",""]
    (OUT/"report.md").write_text("\n".join(md),encoding="utf-8")
    for c in cases:
        print("\n"+"="*80); print(f"[{c['case_id']}] 고객: {c['customer_input']}")
        for k,label in (("single_rag","Single RAG"),("multi_agent","Multi-Agent")):
            r=c[k]; print(f"\n--- {label} ---"); print(f"{r['status']} / {r['guidance_status']} / awaiting={r['awaiting_customer_input']}")
            print("답변:",r["message"])
            if r["followup_questions"]:
                print("추가질문:"); [print(" -",q) for q in r["followup_questions"]]
            if r["multi_handoffs"]:
                print("handoff:"); [print(" -",h["reason"]) for h in r["multi_handoffs"]]
    print("\n"+json.dumps({"status":payload["status"],"git_sha":sha,"provider":provider,
        "output_dir":str(OUT.relative_to(ROOT)).replace("\\","/"),"conclusions":conclusions},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
