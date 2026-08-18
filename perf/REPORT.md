# Gacha Pull API — Load Test Report

> Manual/Bruno test บอกได้แค่ว่า API "ตอบถูก" แต่ไม่บอกว่า "รับไหวกี่คนพร้อมกัน" — รอบนี้เลยลองหาคำตอบด้วย JMeter

ทดสอบด้วย **Apache JMeter** ยิงทั้ง 4 endpoint (`/pull`, `/pull-x10`, `/rates`, `/pity/{user_id}`) พร้อมกัน ไล่เพิ่มจำนวน concurrent users ทีละสเต็ป เพื่อหาว่าระบบรับโหลดได้แค่ไหนก่อนที่ performance จะเริ่มแย่ลง

## วิธีทดสอบ

- เปิด server ไว้ (`uvicorn api.main:app --host 127.0.0.1 --port 8000`)
- Thread Group: Ramp-up 10s, Duration 30s ต่อรอบ, ไล่เพิ่ม Number of Threads: 50 → 100 → 200 → 500
- เช็คแค่ Response Code (200) ระหว่างรันโหลด — ปิด content assertion กับ View Results Tree ไว้ เพื่อไม่ให้ overhead ของ JMeter เองมากวนผลลัพธ์
- เก็บผลด้วย Aggregate Report → export เป็น CSV ทุกรอบ (ดูไฟล์เต็มได้ที่ [`result/`](./result))

## ผลลัพธ์

| Concurrent Users | Average | 90% Line | 99% Line | Max | Throughput | Error % |
|---|---|---|---|---|---|---|
| 50  | 187ms  | 310ms  | 461ms  | 545ms  | 221 req/sec | 0.000% |
| 100 | 314ms  | 423ms  | 544ms  | 602ms  | 264 req/sec | 0.000% |
| 200 | 588ms  | 794ms  | 907ms  | 933ms  | **280 req/sec** (peak) | 0.000% |
| 500 | 1625ms | 2113ms | 4677ms | 4965ms | 247 req/sec ↓ | 0.000% |

## สรุปผล

Gacha API รับ concurrent users ได้ดีจนถึงประมาณ **150–200 users** — throughput ยังโตตามโหลด (peak ~280 req/sec) และ response time ยังอยู่ในเกณฑ์ใช้งานได้ (90% ของ request ตอบกลับภายใน ~800ms)

พอเกิน 200 users ไปถึง 500 users ระบบเริ่ม **overload จริง**:
- Throughput **ลดลง** จาก 280 → 247 req/sec ทั้งที่ยิง user เยอะขึ้น (ไม่ใช่แค่อิ่มตัวคงที่ แต่แย่ลงจริง)
- Response time พุ่งเกือบ 3 เท่า (588ms → 1625ms average) endpoint `/pull` แย่สุด (สูงสุดเกือบ 5 วินาที)

ที่น่าสนใจคือ **ไม่พบ HTTP error เลยแม้แต่ตัวเดียว (0.000%)** ในทุกรอบ แม้ที่ 500 users — เพราะ endpoint เขียนเป็น sync function (`def` ไม่ใช่ `async def`) FastAPI จึงรันผ่าน thread pool ที่มีขนาดจำกัด request ส่วนเกินเลยแค่ต่อคิวรอนานขึ้นเรื่อยๆ แทนที่จะถูก reject — ระบบ "ไม่พังแบบ error" แต่ "ช้าจนใช้งานจริงไม่ได้"

## Takeaway

- Capacity ที่ใช้งานได้จริง (practical capacity): **~150-200 concurrent users**
- Throughput ceiling: **~280 req/sec**
- ถ้าจะรองรับโหลดสูงกว่านี้ ต้องแก้ endpoint ให้เป็น `async def` หรือเพิ่มจำนวน worker process (`uvicorn --workers`) — แต่ต้องระวังเรื่อง in-memory state (`USER_STATE`) ที่ตอนนี้แชร์กันแค่ใน process เดียว ถ้าแยก worker จะทำให้ pity counter ไม่ sync กันข้าม process

## สิ่งที่ตั้งใจไม่ทำ (out of scope)

- หา hard breaking point ที่ error % เริ่ม > 0% จริง (ต้องยิงเกิน 500 users ต่อ)
- Soak/Endurance test (รันโหลดต่อเนื่องยาวๆ ดู memory leak จาก in-memory state ที่โตขึ้นเรื่อยๆ)
- ทดสอบผลกระทบตอนรันแบบ multi-worker
