import asyncio
sem = asyncio.Semaphore(3)
async def worker(id):
    async with sem:
        print(f"start {id}")
        await asyncio.sleep(1)
        print(f"end {id}")
async def main():
    tasks = [worker(i) for i in range(10)]
    await asyncio.gather(*tasks)

asyncio.run(main())