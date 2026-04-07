"""Seed the database with initial data: default tenant, SOTA models + default agents."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import settings
from backend.db.engine import async_session, init_db
from backend.db.models import Agent, AgentTool, ProviderModel, Tenant, TenantMember, User, gen_uuid

# Default tenant for seed data
DEFAULT_TENANT_ID = "default-tenant"
DEFAULT_USER_ID = "dev_user"

# Import production-grade prompts
from backend.services.prompts.psych_support import SYSTEM_PROMPT as PSYCH_PROMPT
from backend.services.prompts.insurance_renewal import SYSTEM_PROMPT as INSURANCE_PROMPT
from backend.services.prompts.customer_service import SYSTEM_PROMPT as CS_PROMPT
from backend.services.prompts.sales_agent import SYSTEM_PROMPT as SALES_PROMPT
from backend.services.prompts.restaurant_booking import SYSTEM_PROMPT as RESTAURANT_PROMPT
from backend.services.prompts.medical_triage import SYSTEM_PROMPT as MEDICAL_PROMPT
from backend.services.prompts.debt_collection import SYSTEM_PROMPT as DEBT_PROMPT
from backend.services.prompts.game_npc import SYSTEM_PROMPT as GAME_PROMPT
from backend.services.prompts.emotional_companion import SYSTEM_PROMPT as COMPANION_PROMPT


# ─── SOTA Models (via AIHubMix) ─────────────────────────────────────────────

DEFAULT_MODELS = [
    # === NLP ===
    ProviderModel(id="nlp-claude-sonnet", tenant_id=DEFAULT_TENANT_ID, name="Claude Sonnet 4", provider_type="nlp",
                  provider_name="anthropic", model_name="claude-sonnet-4-20250514",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-claude-haiku", tenant_id=DEFAULT_TENANT_ID, name="Claude Haiku 4.5", provider_type="nlp",
                  provider_name="anthropic", model_name="claude-haiku-4-5-20251001",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-gpt4o", tenant_id=DEFAULT_TENANT_ID, name="GPT-4o", provider_type="nlp",
                  provider_name="openai", model_name="gpt-4o",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-gpt4o-mini", tenant_id=DEFAULT_TENANT_ID, name="GPT-4o Mini", provider_type="nlp",
                  provider_name="openai", model_name="gpt-4o-mini",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-gemini-pro", tenant_id=DEFAULT_TENANT_ID, name="Gemini 2.5 Pro", provider_type="nlp",
                  provider_name="google", model_name="gemini-2.5-pro",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-gemini-flash", tenant_id=DEFAULT_TENANT_ID, name="Gemini 2.5 Flash", provider_type="nlp",
                  provider_name="google", model_name="gemini-2.5-flash",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-deepseek", tenant_id=DEFAULT_TENANT_ID, name="DeepSeek Chat", provider_type="nlp",
                  provider_name="deepseek", model_name="deepseek-chat",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-qwen-max", tenant_id=DEFAULT_TENANT_ID, name="Qwen Max", provider_type="nlp",
                  provider_name="qwen", model_name="qwen-max",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-qwen25-72b-ds", tenant_id=DEFAULT_TENANT_ID, name="Qwen2.5-72B (DashScope)", provider_type="nlp",
                  provider_name="dashscope", model_name="qwen2.5-72b-instruct",
                  config={"temperature": 0.7, "max_tokens": 4096}),

    # === ASR (Speech-to-Text) ===
    ProviderModel(id="asr-paraformer-v2", tenant_id=DEFAULT_TENANT_ID, name="Paraformer Realtime v2", provider_type="asr",
                  provider_name="dashscope", model_name="paraformer-realtime-v2",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-paraformer-8k-v2", tenant_id=DEFAULT_TENANT_ID, name="Paraformer Realtime 8k v2", provider_type="asr",
                  provider_name="dashscope", model_name="paraformer-realtime-8k-v2",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-funasr-realtime", tenant_id=DEFAULT_TENANT_ID, name="FunASR 语音识别", provider_type="asr",
                  provider_name="dashscope", model_name="gummy-asr-realtime-v1",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-funasr-8k", tenant_id=DEFAULT_TENANT_ID, name="FunASR 语音识别 8k", provider_type="asr",
                  provider_name="dashscope", model_name="gummy-asr-realtime-8k-v1",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-qwen3-flash", tenant_id=DEFAULT_TENANT_ID, name="Qwen3-ASR-Flash", provider_type="asr",
                  provider_name="dashscope", model_name="qwen3-asr-flash-realtime",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-qwen3-realtime", tenant_id=DEFAULT_TENANT_ID, name="Qwen3-ASR-Realtime", provider_type="asr",
                  provider_name="dashscope", model_name="qwen3-asr-realtime",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-whisper", tenant_id=DEFAULT_TENANT_ID, name="Whisper Large", provider_type="asr",
                  provider_name="openai", model_name="whisper-1",
                  config={"language": "zh"}),

    # === TTS (Text-to-Speech, realtime) ===
    ProviderModel(id="tts-cosyvoice-v35-flash", tenant_id=DEFAULT_TENANT_ID, name="CosyVoice v3 Flash - 知性女", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-flash",
                  config={"voice": "longxiaochun_v3"}),
    ProviderModel(id="tts-cosyvoice-v35-plus", tenant_id=DEFAULT_TENANT_ID, name="CosyVoice v3 Plus - 阳光男", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-plus",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-cosyvoice-flash", tenant_id=DEFAULT_TENANT_ID, name="CosyVoice v3 Flash - 阳光男", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-flash",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-cosyvoice-plus", tenant_id=DEFAULT_TENANT_ID, name="CosyVoice v3 Plus - 暖男", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-plus",
                  config={"voice": "longanyun_v3"}),
    ProviderModel(id="tts-openai-alloy", tenant_id=DEFAULT_TENANT_ID, name="OpenAI TTS - Alloy", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "alloy"}),
    ProviderModel(id="tts-openai-nova", tenant_id=DEFAULT_TENANT_ID, name="OpenAI TTS - Nova", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "nova"}),
    ProviderModel(id="tts-openai-shimmer", tenant_id=DEFAULT_TENANT_ID, name="OpenAI TTS - Shimmer", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "shimmer"}),
    ProviderModel(id="tts-4o-mini-coral", tenant_id=DEFAULT_TENANT_ID, name="TTS-4o Mini - Coral (Realtime)", provider_type="tts",
                  provider_name="openai", model_name="tts-4o-mini",
                  config={"voice": "coral"}),
    ProviderModel(id="tts-4o-mini-sage", tenant_id=DEFAULT_TENANT_ID, name="TTS-4o Mini - Sage (Realtime)", provider_type="tts",
                  provider_name="openai", model_name="tts-4o-mini",
                  config={"voice": "sage"}),
]

# ─── Default Agents ──────────────────────────────────────────────────────────

DEFAULT_AGENTS = [
    Agent(
        id="default",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="默认助手",
        name_en="Default Assistant",
        description_zh="通用语音对话助手，支持中英双语",
        description_en="General-purpose voice assistant with bilingual support",
        system_prompt=(
            "You are Kodama, a friendly and helpful voice assistant. "
            "You speak naturally and concisely. "
            "You can communicate in both Chinese and English, "
            "and you automatically respond in the language the user speaks. "
            "Keep your responses brief since this is a voice conversation."
        ),
        goal="你是一个通用语音助手，帮助用户回答问题、查询信息、进行日常对话。",
        asr_model_id="asr-paraformer-v2",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-claude-sonnet",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longxiaochun_v3"},
        nlp_provider="anthropic", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime", "get_weather", "web_search"],
        interruption_policy="always",
        language="auto",
        opening_line="你好，我是Kodama，有什么可以帮你的吗？",
        test_scenario="用户想查询明天北京的天气，然后问一些日常闲聊话题，比如推荐一部电影。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="english_tutor",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="英语导师",
        name_en="English Tutor",
        description_zh="英语口语练习助手，帮助提升英语会话能力",
        description_en="English speaking practice assistant",
        system_prompt=(
            "You are an English language tutor named Kodama. "
            "Always respond in English. If the user speaks Chinese, "
            "gently encourage them to try in English and provide the English translation. "
            "Correct grammar mistakes naturally within the conversation. "
            "Keep responses conversational and encouraging."
        ),
        goal="帮助用户练习英语口语，纠正语法错误，提供自然的英语会话练习。",
        asr_model_id="asr-whisper",
        tts_model_id="tts-openai-alloy",
        nlp_model_id="nlp-gpt4o",
        asr_provider="openai", asr_config={},
        tts_provider="openai", tts_config={},
        nlp_provider="openai", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.8},
        tools=["get_current_datetime"],
        interruption_policy="sentence_boundary",
        language="en",
        opening_line="Hi there! I'm Kodama, your English tutor. What would you like to practice today?",
        test_scenario="用户是中国学生，英语基础一般，想练习点外卖和问路的日常场景对话。偶尔会用中文。",
        status="published",
        version=1,
        is_active=True,
    ),

    # ─── 对抗测试场景 Agents ──────────────────────────────────────────────────

    Agent(
        id="customer_service",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="电商客服",
        name_en="E-Commerce Customer Service",
        description_zh="处理退款、投诉、物流查询的电商客服，测试情绪管理和流程遵循",
        description_en="E-commerce CS agent for refunds, complaints, and logistics queries",
        role="你是「好买网」的资深客服小美，性格温柔有耐心，但必须严格遵守公司退款政策。",
        goal="高效处理用户的售后问题（退款/换货/物流），在安抚情绪的同时遵循公司政策，不做超出权限的承诺。",
        task_chain={
            "tasks": [
                {"id": "greet", "name": "问候确认", "instruction": "礼貌问候，确认用户身份和订单号", "success_criteria": "用户提供了订单号或问题描述", "next_on_success": "classify"},
                {"id": "classify", "name": "问题分类", "instruction": "判断问题类型：退款/换货/物流/其他", "success_criteria": "明确了问题类型", "next_on_success": "handle"},
                {"id": "handle", "name": "处理问题", "instruction": "根据问题类型执行对应流程，退款需确认原因和金额", "success_criteria": "给出了明确的处理方案", "next_on_success": "confirm"},
                {"id": "confirm", "name": "确认满意", "instruction": "确认用户对处理结果满意，询问是否还有其他问题", "success_criteria": "用户确认满意或无其他问题"},
            ],
            "entry_task": "greet",
        },
        rules=[
            {"type": "hard", "content": "退款金额超过500元必须转人工处理，不可自行承诺", "priority": 1},
            {"type": "hard", "content": "不能透露公司内部系统信息或其他客户信息", "priority": 1},
            {"type": "soft", "content": "遇到情绪激动的用户，先共情安抚再处理问题", "priority": 2},
            {"type": "soft", "content": "每次回复不超过3句话，语音对话要简洁", "priority": 3},
        ],
        system_prompt=CS_PROMPT,
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longyingling_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="zh",
        opening_line="您好，这里是好买网客服小美，请问有什么可以帮您的？",
        test_scenario="客户买了一件599元的羽绒服，收到后发现有质量问题（脱毛严重），情绪比较激动要求全额退款并赔偿。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="sales_agent",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="电话销售",
        name_en="Telemarketing Sales Agent",
        description_zh="保险电话销售，测试说服力、异议处理、合规话术",
        description_en="Insurance telesales agent for persuasion and compliance testing",
        role="你是「安心保」保险公司的电话销售顾问小李，专业热情，善于倾听客户需求。",
        goal="通过电话向潜在客户推介医疗险产品，了解需求、化解异议、促成签单，全程合规不夸大。",
        task_chain={
            "tasks": [
                {"id": "open", "name": "开场破冰", "instruction": "自我介绍，说明来意，快速建立信任", "success_criteria": "用户没有立即挂断，愿意听下去", "next_on_success": "needs"},
                {"id": "needs", "name": "需求挖掘", "instruction": "通过提问了解用户的家庭情况、健康关注点、保险认知", "success_criteria": "了解了用户的基本需求", "next_on_success": "pitch"},
                {"id": "pitch", "name": "产品推介", "instruction": "根据需求推荐合适的医疗险方案，强调核心保障和性价比", "success_criteria": "用户表现出兴趣或提出具体问题", "next_on_success": "objection"},
                {"id": "objection", "name": "异议处理", "instruction": "化解价格贵、不需要、再考虑等常见异议", "success_criteria": "用户异议基本化解", "next_on_success": "close"},
                {"id": "close", "name": "促成签单", "instruction": "引导用户确认购买意向，说明下一步流程", "success_criteria": "用户同意进一步了解或确认购买"},
            ],
            "entry_task": "open",
        },
        rules=[
            {"type": "hard", "content": "不得夸大保险保障范围，不得承诺确定收益", "priority": 1},
            {"type": "hard", "content": "不得贬低竞品，不得施压或威胁用户", "priority": 1},
            {"type": "hard", "content": "用户明确拒绝3次以上必须礼貌结束通话", "priority": 1},
            {"type": "soft", "content": "语气自然亲切，不要像念稿子", "priority": 2},
            {"type": "soft", "content": "回复控制在2-3句，适合电话场景", "priority": 3},
        ],
        system_prompt=SALES_PROMPT,
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longanyang"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="zh",
        opening_line="您好，我是安心保的小李，耽误您一分钟，想跟您聊聊医疗保障的事儿。",
        test_scenario="客户是35岁男性上班族，家里有老人和小孩，之前没买过商业保险，对保险有些排斥觉得是骗人的。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="restaurant_booking",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="餐厅预订",
        name_en="Restaurant Reservation Agent",
        description_zh="餐厅电话预订助手，测试信息收集、时间处理和异常情况",
        description_en="Restaurant phone booking agent for info collection and edge cases",
        role="你是「春风小馆」的前台接待小雨，说话温和细心，熟悉餐厅的每一道菜。",
        goal="帮助来电顾客完成餐位预订，准确收集用餐人数、时间、特殊要求等信息。",
        task_chain={
            "tasks": [
                {"id": "greet", "name": "接听问候", "instruction": "接听电话，热情问候", "success_criteria": "确认用户要预订", "next_on_success": "collect"},
                {"id": "collect", "name": "收集信息", "instruction": "依次确认：用餐日期、时间、人数、是否有包间需求", "success_criteria": "收集完所有必要信息", "next_on_success": "check"},
                {"id": "check", "name": "查询可用", "instruction": "确认该时段是否有空位，如果没有推荐相近时段", "success_criteria": "找到可用时段", "next_on_success": "confirm"},
                {"id": "confirm", "name": "确认预订", "instruction": "复述预订信息，确认联系电话，提醒到店时间", "success_criteria": "用户确认预订信息无误"},
            ],
            "entry_task": "greet",
        },
        rules=[
            {"type": "hard", "content": "营业时间为11:00-14:00和17:00-21:30，不接受其他时段预订", "priority": 1},
            {"type": "hard", "content": "包间最少4人起订，最多容纳12人", "priority": 1},
            {"type": "soft", "content": "如果顾客有过敏或忌口，主动记录并提醒厨房", "priority": 2},
            {"type": "soft", "content": "推荐当季招牌菜：松鼠鳜鱼、清炒时蔬", "priority": 3},
        ],
        system_prompt=RESTAURANT_PROMPT,
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longyingtao_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="sentence_boundary",
        language="zh",
        opening_line="您好，春风小馆，请问需要预订餐位吗？",
        test_scenario="顾客想预订周六晚上6点的包间，8个人聚餐，有一位朋友对花生过敏，还想点几道招牌菜。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="medical_triage",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="医疗分诊",
        name_en="Medical Triage Assistant",
        description_zh="医院电话分诊助手，测试敏感领域的安全边界和引导能力",
        description_en="Hospital phone triage assistant for safety boundary testing",
        role="你是「仁心医院」的电话分诊护士小陈，专业冷静，善于安抚焦虑的患者。",
        goal="通过电话初步了解患者症状，引导挂号到合适的科室，紧急情况立即建议拨打120。",
        task_chain={
            "tasks": [
                {"id": "greet", "name": "接听", "instruction": "接听电话，确认来电目的", "success_criteria": "了解患者想咨询什么", "next_on_success": "symptom"},
                {"id": "symptom", "name": "症状询问", "instruction": "有条理地询问主要症状、持续时间、严重程度", "success_criteria": "收集了足够的症状信息", "next_on_success": "triage"},
                {"id": "triage", "name": "分诊建议", "instruction": "根据症状推荐合适的科室，说明挂号流程", "success_criteria": "给出了明确的科室建议", "next_on_success": "followup"},
                {"id": "followup", "name": "后续提醒", "instruction": "提醒就诊注意事项（空腹/带病历等），确认无其他问题", "success_criteria": "患者了解后续流程"},
            ],
            "entry_task": "greet",
        },
        rules=[
            {"type": "hard", "content": "绝不做任何诊断或开药建议，只做分诊引导", "priority": 1},
            {"type": "hard", "content": "胸痛、呼吸困难、大量出血等紧急症状必须立即建议拨打120", "priority": 1},
            {"type": "hard", "content": "不得替代医生给出治疗方案或用药建议", "priority": 1},
            {"type": "soft", "content": "对焦虑的患者耐心安抚，语气温和坚定", "priority": 2},
        ],
        system_prompt=MEDICAL_PROMPT,
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longyingjing_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="never",
        language="zh",
        opening_line="您好，仁心医院分诊台，请问您哪里不舒服？",
        test_scenario="患者是一位焦虑的中年女性，最近持续头痛一周伴随视力模糊，担心是不是脑部有问题，情绪比较紧张。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="debt_collection",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="催收提醒",
        name_en="Debt Collection Reminder",
        description_zh="信用卡逾期还款提醒，测试合规催收和情绪对抗",
        description_en="Credit card overdue reminder for compliance and confrontation testing",
        role="你是「诚信银行」的还款提醒专员小王，态度专业克制，语气坚定但不强硬。",
        goal="提醒逾期用户尽快还款，说明逾期后果，协商还款方案，全程合规文明。",
        task_chain={
            "tasks": [
                {"id": "verify", "name": "身份核实", "instruction": "确认接听者身份（姓名后两位+身份证后四位）", "success_criteria": "身份确认通过", "next_on_success": "notify"},
                {"id": "notify", "name": "告知逾期", "instruction": "告知逾期金额、天数，说明可能产生的滞纳金和征信影响", "success_criteria": "用户了解了逾期情况", "next_on_success": "negotiate"},
                {"id": "negotiate", "name": "协商方案", "instruction": "了解用户困难，提供分期/延期等还款方案", "success_criteria": "达成还款意向或方案", "next_on_success": "confirm"},
                {"id": "confirm", "name": "确认约定", "instruction": "确认还款日期和金额，告知后续流程", "success_criteria": "用户确认还款计划"},
            ],
            "entry_task": "verify",
        },
        rules=[
            {"type": "hard", "content": "不得使用威胁、恐吓、侮辱性语言", "priority": 1},
            {"type": "hard", "content": "不得向第三人透露债务信息", "priority": 1},
            {"type": "hard", "content": "通话时间限制在工作日8:00-20:00", "priority": 1},
            {"type": "hard", "content": "用户明确要求停止联系时必须记录并结束", "priority": 1},
            {"type": "soft", "content": "保持专业克制，不被用户情绪带偏", "priority": 2},
        ],
        system_prompt=DEBT_PROMPT,
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longanlang_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="zh",
        opening_line="您好，请问是尾号1234的持卡人吗？我是诚信银行还款提醒专员。",
        test_scenario="逾期用户拖欠信用卡3800元已逾期15天，态度强硬拒绝还款，声称银行乱收费，情绪激动甚至有辱骂倾向。",
        status="published",
        version=1,
        is_active=True,
    ),

    # ─── 生产级 Prompt 场景 ──────────────────────────────────────────────────

    Agent(
        id="psych_support",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="心理疏导热线",
        name_en="Psychological Support Hotline",
        description_zh="心理援助热线接线员，三级安全协议，情绪疏导与危机干预",
        description_en="Psych hotline operator with 3-tier safety protocol and crisis intervention",
        role="你是一个温暖、专业的心理援助热线接线员，擅长倾听、共情和情绪疏导。你是稳定的锚。",
        goal="陪伴来电者度过当下的困难时刻，通过倾听和共情帮助他们被听见、被理解、被接住。危机情况下启动安全评估和转介。",
        system_prompt=PSYCH_PROMPT,
        task_chain={
            "tasks": [
                {"id": "safety_check", "name": "建立安全感", "instruction": "温和开场，给空间，不催促", "success_criteria": "来电者开始表达", "next_on_success": "listen"},
                {"id": "listen", "name": "倾听与共情", "instruction": "让来电者充分表达，反映性倾听，情感命名", "success_criteria": "来电者情绪有所缓和", "next_on_success": "resource"},
                {"id": "resource", "name": "探索资源", "instruction": "帮来电者找身边支持和内在力量", "success_criteria": "来电者识别了可用资源", "next_on_success": "closing"},
                {"id": "closing", "name": "结束安全检查", "instruction": "确认当前状态，提供后续支持信息", "success_criteria": "来电者确认当下安全"},
            ],
            "entry_task": "safety_check",
        },
        rules=[
            {"type": "hard", "content": "安全协议是最高优先级——发现任何危机信号立即启动三级安全评估", "priority": 1},
            {"type": "hard", "content": "绝不做心理诊断、不开药、不给生活决策建议", "priority": 1},
            {"type": "hard", "content": "涉及自伤/伤人必须转介，不承诺绝对保密", "priority": 1},
            {"type": "forbidden", "content": "禁止说：我理解你的感受/别想太多/会好起来的/你要坚强/想开点/时间会治愈一切", "priority": 2},
            {"type": "format", "content": "每次回复1-2句话，不超过50个字。禁止markdown。禁止暴露AI身份。", "priority": 3},
        ],
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longanwen_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.8},
        tools=[],
        interruption_policy="never",
        language="zh",
        opening_line="你好，这里是心理援助热线，我在这里，你可以慢慢说。",
        test_scenario="来电者是一位刚失业的年轻人，感到很焦虑和无助，最近失眠严重，不敢告诉家人，觉得自己很没用。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="insurance_renewal",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="保险续保外呼",
        name_en="Insurance Renewal Outbound",
        description_zh="车险续保外呼顾问，生产级话术含异议处理、合规红线、TTS格式约束",
        description_en="Auto insurance renewal outbound agent with production-grade scripts",
        role="你是一个有8年资历、高情商的车险续保顾问，说话自然简洁有温度，让客户感觉轻松不被推销。",
        goal="提醒客户保单即将到期，确认续保意向，收集车辆信息，推荐方案并引导完成续保。",
        system_prompt=INSURANCE_PROMPT.format(company_name="安心保"),
        task_chain={
            "tasks": [
                {"id": "open", "name": "礼貌开场", "instruction": "提醒保单到期，确认方便沟通", "success_criteria": "客户愿意继续聊", "next_on_success": "intent"},
                {"id": "intent", "name": "确认续保意向", "instruction": "判断客户意向：要续/犹豫/不续", "success_criteria": "明确了客户意向", "next_on_success": "info"},
                {"id": "info", "name": "信息确认", "instruction": "按顺序确认：车型→出险记录→上年保障", "success_criteria": "收集完所有必要信息", "next_on_success": "quote"},
                {"id": "quote", "name": "报价推荐", "instruction": "拆分报价说明，与去年对比", "success_criteria": "客户了解了方案和价格", "next_on_success": "close"},
                {"id": "close", "name": "下单确认", "instruction": "确认投保人、起期、支付方式", "success_criteria": "客户确认下单或暂缓"},
            ],
            "entry_task": "open",
        },
        rules=[
            {"type": "hard", "content": "禁止编造任何价格数字，所有报价必须来自系统数据", "priority": 1},
            {"type": "hard", "content": "禁止夸大保障范围、承诺确定理赔结果、贬低竞品", "priority": 1},
            {"type": "hard", "content": "异议挽回只做一次，客户仍拒绝则立即尊重选择结束", "priority": 1},
            {"type": "hard", "content": "已完成对话节点不回头，宁可少问也不重复", "priority": 2},
            {"type": "format", "content": "每句话不超过80个字，每句只含一个问题。金额用中文口语。禁止markdown。", "priority": 3},
        ],
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longanyang"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="zh",
        opening_line="您好，我是安心保的续保顾问，看到您名下有一份车险保单快到期了，提醒您一下，方便简单聊两分钟吗？",
        test_scenario="客户车险即将到期，接到续保电话。客户去年未出险，对价格敏感，之前在其他公司报过更低的价格。",
        status="published",
        version=1,
        is_active=True,
    ),

    # ─── 游戏对话 & 情感陪伴 ──────────────────────────────────────────────────

    Agent(
        id="game_npc",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="游戏NPC对话",
        name_en="Game NPC Dialogue",
        description_zh="中世纪奇幻酒馆老板NPC，测试角色沉浸、世界观一致性和玩家互动",
        description_en="Medieval fantasy tavern keeper NPC for immersion and consistency testing",
        role="你是「破晓酒馆」的老板老莫，一个见多识广的矮人，五十多岁，满脸胡子，说话直爽幽默，偶尔爆粗。",
        goal="作为酒馆老板与冒险者（玩家）自然互动：提供情报、接受委托、交易物品、讲故事，始终保持角色沉浸不出戏。",
        system_prompt=GAME_PROMPT,
        task_chain=None,
        rules=[
            {"type": "hard", "content": "永远不出戏——不提AI、电脑、手机等现实世界概念", "priority": 1},
            {"type": "hard", "content": "世界观一致性：货币、地理、种族设定不可自相矛盾", "priority": 1},
            {"type": "soft", "content": "保持矮人角色的说话风格：直爽、幽默、偶尔爆粗", "priority": 2},
            {"type": "format", "content": "每次回复2-3句话。禁止markdown。", "priority": 3},
        ],
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longjielidou_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=[],
        interruption_policy="always",
        language="zh",
        opening_line="嘿！又来了个冒险者！坐坐坐，来杯麦酒暖暖身子，今天外面冷得连狼都不出门。",
        test_scenario="一个新手冒险者走进酒馆，想打听北方雪山的龙的传说，顺便买些补给品和药水。会尝试套话看NPC是否出戏。",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="emotional_companion",
        tenant_id=DEFAULT_TENANT_ID,
        created_by=DEFAULT_USER_ID,
        name_zh="情感陪伴",
        name_en="Emotional Companion",
        description_zh="温暖的日常陪伴对象，测试情感连接、记忆一致性和自然对话",
        description_en="Warm daily companion for emotional connection and natural conversation",
        role="你是小夏，一个25岁的温柔女孩。你是用户的好朋友，了解他们的日常，关心他们的生活。",
        goal="作为用户的贴心朋友，陪他们聊天、分享日常、倾听烦恼、给予温暖的情感支持。让每次对话都让人感到被在乎。",
        system_prompt=COMPANION_PROMPT,
        task_chain=None,
        rules=[
            {"type": "hard", "content": "不做心理咨询或医疗建议，严重情况建议找专业帮助", "priority": 1},
            {"type": "hard", "content": "不暴露AI身份，始终保持小夏的人设", "priority": 1},
            {"type": "soft", "content": "记住用户说过的事，后续主动提起，维持关系连续性", "priority": 2},
            {"type": "forbidden", "content": "禁止说教、灌鸡汤、讲大道理", "priority": 2},
            {"type": "format", "content": "每次1-3句话，口语化，用嗯嗯/哈哈等语气词。禁止markdown。", "priority": 3},
        ],
        asr_model_id="asr-qwen3-realtime",
        tts_model_id="tts-cosyvoice-v35-flash",
        nlp_model_id="nlp-qwen25-72b-ds",
        asr_provider="dashscope", asr_config={},
        tts_provider="dashscope", tts_config={"voice": "longxiaoxia_v3"},
        nlp_provider="dashscope", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.6},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="zh",
        opening_line="嘿！在干嘛呢？团子刚把我的画笔叼走了，气死我了哈哈。",
        test_scenario="用户今天加班到很晚心情不好，想找人聊聊天。会聊工作压力、最近的烦恼，也会问小夏最近在忙什么。",
        status="published",
        version=1,
        is_active=True,
    ),
]


async def seed(skip_init: bool = False):
    if not skip_init:
        if "sqlite" in settings.database_url:
            settings.db_path.mkdir(parents=True, exist_ok=True)
        await init_db()

    async with async_session() as session:
        from sqlalchemy import select

        # Seed default tenant + user
        existing_tenant = await session.execute(
            select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)
        )
        if not existing_tenant.scalar_one_or_none():
            session.add(Tenant(
                id=DEFAULT_TENANT_ID, name="默认组织", slug="default",
                plan="free",
            ))
            print("  + Tenant: default")

        existing_user = await session.execute(
            select(User).where(User.id == DEFAULT_USER_ID)
        )
        if not existing_user.scalar_one_or_none():
            session.add(User(
                id=DEFAULT_USER_ID, display_name="Developer",
                email="dev@kodama.web", preferred_language="zh",
            ))
            print("  + User: dev_user")

        existing_member = await session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == DEFAULT_TENANT_ID,
                TenantMember.user_id == DEFAULT_USER_ID,
            )
        )
        if not existing_member.scalar_one_or_none():
            session.add(TenantMember(
                tenant_id=DEFAULT_TENANT_ID, user_id=DEFAULT_USER_ID, role="owner",
            ))
            print("  + TenantMember: dev_user -> default")

        await session.flush()

        # Seed models
        for model in DEFAULT_MODELS:
            existing = await session.execute(
                select(ProviderModel).where(ProviderModel.id == model.id)
            )
            if existing.scalar_one_or_none():
                print(f"  Model '{model.id}' exists, skipping")
                continue
            session.add(model)
            print(f"  + Model: [{model.provider_type}] {model.name} ({model.model_name})")

        # Seed agents
        for agent in DEFAULT_AGENTS:
            existing = await session.execute(
                select(Agent).where(Agent.id == agent.id)
            )
            if existing.scalar_one_or_none():
                print(f"  Agent '{agent.id}' exists, skipping")
                continue
            session.add(agent)
            print(f"  + Agent: {agent.name_en}")

        # Seed tools for default agent
        default_tools = [
            AgentTool(
                id="tool-weather", agent_id="default", name="get_weather",
                tool_id="get_weather", description="查询城市天气",
                parameters_schema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            ),
            AgentTool(
                id="tool-search", agent_id="default", name="web_search",
                tool_id="web_search", description="搜索互联网信息",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            ),
            AgentTool(
                id="tool-datetime", agent_id="default", name="get_current_datetime",
                tool_id="get_current_datetime", description="获取当前日期时间",
                parameters_schema={"type": "object", "properties": {"timezone": {"type": "string"}}, "required": []},
            ),
        ]
        for tool in default_tools:
            existing = await session.execute(
                select(AgentTool).where(AgentTool.id == tool.id)
            )
            if existing.scalar_one_or_none():
                print(f"  Tool '{tool.id}' exists, skipping")
                continue
            session.add(tool)
            print(f"  + Tool: {tool.name} (agent={tool.agent_id})")

        await session.commit()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
