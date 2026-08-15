# Gacha Pull API

> A backend service for a gacha-style pull system — built to answer the question nobody should ask at 3 AM: "What if I pull one more time?"
> Supports single and multi pulls, drop-rate lookup, and per-player pity tracking. In-memory state included. Regret not included.

โปรเจกต์นี้คือ **ระบบสุ่มกาชาจำลอง** (mock gacha pull system) เขียน API spec ก่อนแล้วค่อยเขียนโค้ดตาม (spec-first) พร้อมชุดเทสทั้งแบบ manual test case และ automated test ด้วย Bruno

## ระบบทำอะไรได้บ้าง

มี 4 endpoint:

| Method | Path | ทำอะไร |
|---|---|---|
| `POST` | `/pull` | สุ่มไอเทม 1 ครั้ง |
| `POST` | `/pull-x10` | สุ่มไอเทม 10 ครั้งรวด — การันตีว่าใน 10 ใบต้องมี SR ขึ้นไปอย่างน้อย 1 ใบ |
| `GET` | `/rates` | ดูอัตราดรอปของแต่ละ rarity (N/R/SR/SSR) |
| `GET` | `/pity/{user_id}` | ดูว่า user คนนั้นสุ่มติดกันมากี่ครั้งแล้วโดยยังไม่ได้ SSR |

**กติกาที่ตั้งไว้:**
- อัตราดรอป: N 60% / R 27% / SR 10% / SSR 3%
- Pity: สุ่มติดกัน 50 ครั้งไม่ได้ SSR → ครั้งถัดไปการันตี SSR ทันที แล้วรีเซ็ตตัวนับ
- State ทั้งหมดเก็บแบบ in-memory (ไม่มี database จริง) — restart server แล้วข้อมูลหายหมด ตั้งใจให้เป็นแบบนี้เพื่อเน้นที่การเทส ไม่ใช่ระบบ production จริง

ตัวอย่างการเรียกใช้งานจริง:

```bash
curl -X POST http://localhost:8000/pull -H "Content-Type: application/json" -d '{"user_id":"player_001"}'
```

```json
{"user_id":"player_001","item":{"item_id":"itm_n_004","name":"Very Ordinary Stick","rarity":"N"},"pity_count":1,"pity_triggered":false}
```

## Tech Stack

- **FastAPI** (Python) — ตัว API
- **OpenAPI 3.0** — เขียน spec เองก่อนเขียนโค้ด (spec-first)
- **Bruno + Bruno CLI** — automated API testing

## โครงสร้างโปรเจกต์

```
Gacha_API/
├── api/
│   └── main.py              # โค้ด FastAPI ทั้ง 4 endpoint (in-memory)
├── docs/
│   ├── openapi.yaml          # API spec แบบ spec-first
│   └── Test_Case.xlsx       # manual test case 31 เคส + ผลรันจริง + methodology
└── tests/                    # Bruno collection — automated test ตรงกับทุกเคสใน Test_Case.xlsx
    ├── pull/
    ├── pull-x10/
    ├── rates/
    ├── pity/
    └── statistical/
```

## วิธีรันเอง

```bash
# 1. สร้าง virtual environment (ทำครั้งเดียว)
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS/Linux

# 2. ติดตั้ง dependencies
pip install fastapi "uvicorn[standard]"

# 3. รัน server
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

เปิด `http://127.0.0.1:8000/docs` จะเห็นหน้า Swagger UI ที่ auto-generate จาก spec ให้ลองยิงเล่นได้เลย

## วิธีเทสด้วย Bruno

1. เปิด Bruno app → **Open Collection** → เลือกโฟลเดอร์ `tests/`
2. เลือก environment เป็น **Local**
3. ต้องรัน server (ขั้นตอนด้านบน) ทิ้งไว้ก่อนเสมอ
4. คลิกขวาที่โฟลเดอร์ (เช่น `pull/`) หรือที่ตัว collection แล้วเลือก **Run** เพื่อยิงเทสทั้งหมด

หรือใช้ command line (ต้องลง `npm install -g @usebruno/cli` ก่อน):

```bash
cd tests
bru run . --env Local -r
```

## สรุปผลเทส

ทดสอบไว้ทั้งหมด **31 เคส** แบ่งเป็น Positive / Negative / Boundary / Statistical ครอบคลุมทั้ง 4 endpoint — รายละเอียดเต็มดูได้ที่ `docs/Test_Case.xlsx` (มีทั้ง Expected Result, Actual Result, และเหตุผลของแต่ละการตัดสินใจในการออกแบบเทส เช่น ทำไมถึงไม่ใช้ RNG seed)

เคสที่น่าสนใจที่สุดคือการเทสระบบ pity — เพราะ 3% ต่อครั้งเป็นความน่าจะเป็นที่ไม่คงที่ ไม่สามารถยิงตายตัว 50 ครั้งแล้วเช็คว่าครั้งที่ 51 ต้องได้ SSR (SSR ธรรมชาติอาจมาก่อนแล้วรีเซ็ตตัวนับ) วิธีที่ถูกต้องคือยิงจนกว่าตัวนับ pity จะถึง 50 จริงๆ ก่อนค่อยเช็ค — เขียนไว้เป็น loop ใน Bruno เองผ่าน `bru.runner.setNextRequest()`

## สิ่งที่ตั้งใจไม่ทำ (out of scope)

- Concurrency / หลาย request พร้อมกันของ user เดียวกัน (ไม่มี lock ป้องกัน)
- Persistence ข้ามการ restart server
- Authentication / Authorization
- Load/performance testing
