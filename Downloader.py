import asyncio
import pathlib
import random
import re, tqdm
import aiohttp, aiofiles
import orjson, os
import yaml

cfg = pathlib.Path("Config.yaml")
if cfg.exists():
    with open(cfg,encoding="utf-8") as f:
        e = yaml.safe_load(f)
else:
    e = {}
conf = e
work_path = conf.setdefault('work-path',None)


if not work_path:
    cfg.write_text(yaml.dump(e),encoding="utf-8")
    raise Exception("Work path missing")

work_path = pathlib.Path(work_path).resolve()
if not work_path.is_dir():
    raise Exception("Work path does not exist.")

if conf.get('cookie') is None:
    cfg.write_text(yaml.dump(e),encoding="utf-8")
    raise Exception("Missing cookies.")
else:
    cookie = conf.get('cookie')

if not work_path:
    cfg.write_text(yaml.dump(e),encoding="utf-8")
    raise Exception("Work path missing")

async def main():
    async with aiohttp.ClientSession(cookies={"FANBOXSESSID":cookie}) as session:
        session.headers.update({
            'user-agent': conf.setdefault('user-agent',"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36"),
            'accept': 'application/json',
            'origin': 'https://www.fanbox.cc'
        })
        # Open the indexer
        if (work_path / "index_new.json").exists():
            with open((work_path / "index_new.json"),"r",encoding="utf-8") as f:
                indexes = orjson.loads(f.read())
        else:
            indexes = {}
        if not indexes:
            print("Indexes is invalid.")


        sem = asyncio.Semaphore(5)

        async def download_task(url,path:pathlib.Path):
            if path.exists():
                # print(f"{path.name} already exists. Skipping...")
                return
            async with sem:
                while True:
                    await asyncio.sleep(random.uniform(0.5, 1))
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                with tqdm.tqdm(desc=f"{path.name}", unit = 'B', unit_scale = True, total=response.content_length) as pbar:
                                    async with aiofiles.open(path,"wb") as f:
                                        async for content in response.content.iter_any():
                                            await f.write(content)
                                            pbar.update(len(content))
                                        return
                            elif response.status == 500:
                                print(await response.text(), "For URL", url)
                                return
                            elif response.status == 403:
                                print(response.status, "For URL", url)
                                return
                    except (aiohttp.ServerDisconnectedError, aiohttp.ClientConnectionError):
                        await asyncio.sleep(random.uniform(1, 5))
                        continue
                
        tasks = []
        for post_id, post in indexes.items():

            creator_path:pathlib.Path = (work_path / post["creator"])
            if not creator_path.is_dir():
                creator_path.mkdir(exist_ok=True,parents=True)

            san = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F]", "-", post['title']).rstrip(".").rstrip(" ")
            post_path = (creator_path / f"{post_id}-{san}")
            pp = len(post["file"]) > 0 or len(post["image"]) > 0
            #print(pp, post_path.is_dir())
            if not post_path.is_dir() and pp:
                post_path.mkdir(exist_ok=True,parents=True)
            elif not pp and post_path.is_dir():
                os.rmdir(post_path)
            if not "blocks" in post:
                raise DeprecationWarning("Non blocks index is no longer supported.")
            if post["blocks"]:
                # Use the blocks to determine order
                for blk_idx, block in enumerate(post["blocks"]):
                    if block["type"] == "image":
                        image = None
                        if isinstance(post["image"], list):
                            for s_im in post["image"]:
                                if s_im["id"] == block["imageId"]:
                                    image = s_im
                                    break
                        else:
                            # Probably dict
                            image = post["image"][block["imageId"]]
                        if image is None:
                            print("Weird post",post)
                            raise Exception()
                        subname = image['id']
                        if 'name' in image:
                            subname = f"{image['name']}-{image['id']}"
                        tasks.append(download_task(image["originalUrl"], post_path / f"blk-{blk_idx}-{subname}.{image['extension']}"))
                    elif block["type"] == "file":
                        file = post["file"][block["fileId"]]
                        subname = file['id']
                        if 'name' in file:
                            subname = f"{file['name']}-{file['id']}"
                        tasks.append(download_task(file["url"], post_path / f"blk-{blk_idx}-{subname}.{file['extension']}"))
                        
            else:
                # Fall back to images first then files for order.
                for img_idx, image in enumerate(post["image"]):
                    subname = image['id']
                    if "name" in image:
                        subname = f"{image['name']}-{image['id']}"
                    tasks.append(download_task(image["originalUrl"], post_path / f"im-{img_idx}-{subname}.{image['extension']}"))
                for fs_idx, file in enumerate(post["file"]):
                    subname = file['id']
                    if 'name' in file:
                        subname = f"{file['name']}-{file['id']}"
                    tasks.append(download_task(file["url"], post_path / f"fs-{fs_idx}-{subname}.{file['extension']}"))
                
                # No blocks
            # if post["file"]:
            #     if isinstance(post["file"], dict):
            #         itera = post["file"].values()
            #     else:
            #         itera = post["file"]
            #     for file in itera:
            #         #print(file)
            #         if file["name"]:
            #             # Use named file.
            #             tasks.append(download_task(file["url"], post_path / f"{file['name']}.{file['extension']}"))
            #         else:
            #             # Use new blocks format
            #             if "blocks" in post and post["blocks"]:
            #                 img_idx = 0
            #                 for idx, block in enumerate(post["blocks"]):
            #                     if block["type"] == "image" and block["imageId"] == file['id']:
            #                         img_idx = idx
            #                         break
            #                 tasks.append(download_task(file["url"], post_path / f"{img_idx}-{file['id']}.{file['extension']}"))
            #             else:
            #                 tasks.append(download_task(file["url"], post_path / f"{file['id']}.{file['extension']}"))
            # if post["image"]:
            #     if isinstance(post["image"], dict):
            #         itera = post["image"].values()
            #     else:
            #         itera = post["image"]
            #     for idx, img in enumerate(itera):
            #         # print(img)
            #         
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    print("Downloading...")
    asyncio.run(main())