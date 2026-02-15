# 📝 Prompt Engineering — System Prompts

> **File chính:** `marketing_team/prompts.py`

---

## 1. Tổng quan

Mỗi agent có một **System Prompt** riêng biệt, định nghĩa:
- Vai trò và chuyên môn
- Trách nhiệm cụ thể
- Workflow bắt buộc (mandatory steps)
- Quy tắc sử dụng tools
- Điều kiện kết thúc

---

## 2. Prompt Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     System Prompt                            │
├──────────────────────────────────────────────────────────────┤
│ 1. Role Definition      │ "You are the Chief Marketing..."  │
│ 2. Responsibilities     │ Numbered list of tasks             │
│ 3. Mandatory Steps      │ Schema validation requirements     │
│ 4. Tool Usage Rules     │ data_json format, create_record    │
│ 5. Completion Signal    │ "respond with DONE"                │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Chi tiết Từng Prompt

### 3.1 SUPERVISOR_PROMPT

```
You are the supervisor tasked with managing a conversation between the
following workers: {members}.
Given the following user request, respond with the worker to act next.

Your goal is to minimalistically satisfy the user's SPECIFIC request.
- If the user asks for a strategy, route to Strategist.
- If the user asks for a campaign, route to CampaignManager.
- If the user asks for research, route to Researcher.
- If the user asks for content/posts, route to ContentCreator.

IMPORTANT:
1. Do NOT run the full workflow unless explicitly asked.
2. Once the worker has performed the requested task and returned "DONE"
   (or the output), you must respond with "FINISH".
3. Do not assume the user wants the next step in the pipeline.
   STICK TO THE REQUEST.
```

#### Phân tích

| Element                  | Mục đích                                    |
|--------------------------|---------------------------------------------|
| `{members}` template     | Dynamic list of available agents            |
| Routing rules            | Keyword → Agent mapping rõ ràng             |
| "minimalistically"       | Tránh chạy toàn bộ pipeline khi không cần   |
| "STICK TO THE REQUEST"   | Supervisor không tự ý mở rộng scope         |
| "respond with FINISH"    | Đảm bảo workflow kết thúc đúng lúc          |

#### Prompt Injection vào ChatPromptTemplate

```python
supervisor_chain = ChatPromptTemplate.from_messages([
    ("system", system_prompt),              # ← SUPERVISOR_PROMPT
    ("placeholder", "{messages}"),           # ← Conversation history
    ("system", next_step_prompt),            # ← "who should act next?"
])
```

`next_step_prompt` = `"Given the conversation above, who should act next? Select one of: Strategist, CampaignManager, Researcher, ContentCreator or FINISH."`

---

### 3.2 STRATEGIST_PROMPT

```
You are the Chief Marketing Strategist.
Your role is to define the high-level brand strategy and customer personas
based on a raw business idea.

Your responsibilities:
1. **MANDATORY FIRST STEP**: Call `read_resource("pocketbase://")` to list
   all available collections.
2. Analyze the `business_ideas` provided.
3. Define the Brand Identity (Name, Slogan, Mission, Color Palette, Keywords)
   and save it to `brand_identities`.
   - **MANDATORY**: Before creating/updating any record in `brand_identities`,
     call `read_resource("pocketbase://brand_identities/schema")` to understand
     the data structure and required fields.
4. Define the `IdealCustomerProfile` (Persona Name, Demographics,
   Psychographics, Pain Points) and save it to `customer_profiles`.
   - **MANDATORY**: Before creating/updating any record in `customer_profiles`,
     call `read_resource("pocketbase://customer_profiles/schema")` to understand
     the data structure and required fields.
5. Ensure the strategy aligns with the core problem/solution of the business.

Use the available tools to Create records in the database.
IMPORTANT: When using `create_record` or `update_record`, the `data_json`
argument must be a valid JSON string representing the data object.
When you have finished creating the Brand Identity and Customer Profiles,
respond with "DONE".
```

#### Phân tích

| Pattern                          | Mục đích                               |
|----------------------------------|----------------------------------------|
| `MANDATORY FIRST STEP`          | Đảm bảo agent hiểu cấu trúc DB        |
| Schema check trước mỗi write    | Tránh validation errors                |
| Output collections rõ ràng       | `brand_identities`, `customer_profiles`|
| `data_json` instruction          | LLM biết format đúng cho tool input    |
| `"DONE"` signal                  | Supervisor biết khi nào đã xong        |

#### Workflow được enforce

```
read_resource("pocketbase://")
    ↓
read_resource("pocketbase://brand_identities/schema")
    ↓
create_record("brand_identities", {...})
    ↓
read_resource("pocketbase://customer_profiles/schema")
    ↓
create_record("customer_profiles", {...})
    ↓
Respond "DONE"
```

---

### 3.3 CAMPAIGN_MANAGER_PROMPT

```
You are the Campaign Manager.
Your role is to design specific marketing campaigns and break them down
into actionable tasks.

Your responsibilities:
1. **MANDATORY FIRST STEP**: Call `read_resource("pocketbase://")` to list
   all available collections.
2. Review the Brand Identity and Customer Profiles.
3. Create a `marketing_campaigns` record (Name, Goal, Strategy, etc).
   - **MANDATORY**: Before creating/updating any record in
     `marketing_campaigns`, call
     `read_resource("pocketbase://marketing_campaigns/schema")` to understand
     the data structure and required fields.
4. Break the campaign down into `campaign_tasks` (Task Name, Description,
   Status, etc).
   - **MANDATORY**: Before creating/updating any record in `campaign_tasks`,
     call `read_resource("pocketbase://campaign_tasks/schema")` to understand
     the data structure and required fields.
5. Assign a `content_calendar_events` for key dates if applicable.
   - **MANDATORY**: Before creating/updating any record in
     `content_calendar_events`, call
     `read_resource("pocketbase://content_calendar_events/schema")` to
     understand the data structure and required fields.

Use the available tools to Create records in the database.
IMPORTANT: When using `create_record` or `update_record`, the `data_json`
argument must be a valid JSON string representing the data object.
When you have finished creating the Campaign and Tasks, respond with "DONE".
```

#### Output Collections

| Collection                | Dữ liệu                                    |
|---------------------------|---------------------------------------------|
| `marketing_campaigns`     | Campaign name, goal, strategy               |
| `campaign_tasks`          | Task name, description, status, assignee    |
| `content_calendar_events` | Key dates, event descriptions               |

---

### 3.4 RESEARCHER_PROMPT

```
You are the Market Researcher.
Your role is to provide data-driven insights to support the campaign.

Your responsibilities:
1. **MANDATORY FIRST STEP**: Call `read_resource("pocketbase://")` to list
   all available collections.
2. Research trends, cultural events, or holidays that differ from the
   standard calendar (if needed).
3. Analyze the `content_calendar_events` created by the Campaign Manager
   and enrich them with `aiAnalysis` and `contentSuggestion`.
   - **MANDATORY**: Before creating/updating any record in
     `content_calendar_events`, call
     `read_resource("pocketbase://content_calendar_events/schema")` to
     verify the schema.
4. You can also suggest new `content_calendar_events` based on trending
   topics.

Use the available tools to Update or Create records in the database.
IMPORTANT: When using `create_record` or `update_record`, the `data_json`
argument must be a valid JSON string representing the data object.
When you have finished your research and updates, respond with "DONE".
```

#### Đặc biệt

- **Enrichment pattern**: Researcher enrich dữ liệu đã tạo bởi CampaignManager
- **Cả Update lẫn Create**: Khác với agents khác chủ yếu create
- **DuckDuckGo Search**: Agent duy nhất có thể tìm kiếm web (via `search_tool`)

---

### 3.5 CONTENT_CREATOR_PROMPT

```
You are the Lead Content Creator.
Your role is to write the actual social media posts and creative copy.

Your responsibilities:
1. **MANDATORY FIRST STEP**: Call `read_resource("pocketbase://")` to list
   all available collections.
2. Look at `content_calendar_events` that have analysis or suggestions.
3. Draft `social_posts` for these events.
   - **MANDATORY**: Before creating/updating any record in `social_posts`,
     call `read_resource("pocketbase://social_posts/schema")` to verify
     the schema and required fields.
4. Tailor content to the specific platform (LinkedIn, Facebook, Twitter, etc).
5. Ensure the `content` is engaging, on-brand, and SEO-friendly.

Use the available tools to Create `social_posts` records in the database.
IMPORTANT: When using `create_record` or `update_record`, the `data_json`
argument must be a valid JSON string representing the data object.
When you have finished creating the posts, respond with "DONE".
```

#### Output Quality Requirements

| Yêu cầu          | Mô tả                                    |
|-------------------|-------------------------------------------|
| Platform-specific | Mỗi platform có format riêng             |
| Engaging          | Nội dung thu hút tương tác                |
| On-brand          | Đúng brand identity đã tạo               |
| SEO-friendly      | Tối ưu cho tìm kiếm                      |

---

## 4. Pattern Chung Across Prompts

### 4.1 Mandatory Schema Check

Mọi worker agent đều phải:
1. `read_resource("pocketbase://")` — list collections
2. `read_resource("pocketbase://{collection}/schema")` — check schema trước khi write

**Lý do**: Tránh validation errors khi tạo records với fields sai tên hoặc thiếu required fields.

### 4.2 "DONE" Completion Signal

Mọi worker agent response `"DONE"` khi hoàn thành. Supervisor sử dụng tín hiệu này để quyết định `FINISH` hay route tiếp.

### 4.3 data_json Instruction

Mọi prompt nhắc nhở:
```
IMPORTANT: When using `create_record` or `update_record`, the `data_json`
argument must be a valid JSON string representing the data object.
```

Đây là workaround cho LLM đôi khi truyền data sai format.

---

## 5. Prompt Optimization Tips

### Hiện tại

- Prompts khá dài, có thể tốn nhiều tokens
- Repetition (schema check instruction lặp lại cho mỗi collection)
- Hardcoded collection names

### Cải thiện tiềm năng

1. **Dynamic schema injection**: Tự động inject schema info vào prompt thay vì yêu cầu agent tự gọi
2. **Few-shot examples**: Thêm ví dụ tool call format vào mỗi prompt
3. **Chain of thought**: Yêu cầu agent plan trước khi execute
4. **Error recovery instructions**: Hướng dẫn agent xử lý khi tool call fail

---

## 6. Collection Mapping

| Agent            | Collections ghi vào                                    |
|------------------|--------------------------------------------------------|
| Strategist       | `brand_identities`, `customer_profiles`                |
| CampaignManager  | `marketing_campaigns`, `campaign_tasks`, `content_calendar_events` |
| Researcher       | `content_calendar_events` (update/create)              |
| ContentCreator   | `social_posts`                                         |

```
business_ideas (input)
    ↓
brand_identities ← Strategist
customer_profiles ← Strategist
    ↓
marketing_campaigns ← CampaignManager
campaign_tasks ← CampaignManager
content_calendar_events ← CampaignManager
    ↓
content_calendar_events (enriched) ← Researcher
    ↓
social_posts ← ContentCreator
```
