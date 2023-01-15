# Garnet

*Internal Project name: Erossmann*

## What?

Garnet is a simple and fast fantia.jp downloader.

## Why?

The previous downloader had 2 glaring issues:

- Uses requests. Although it's possible to do with threads, asyncio & aiohttp can achieve greater speeds.
- The code looked overly complicated for a simple fantia.jp downloader.

The script is split into 2 parts. The `indexer.py` and `downloader.py`. For Indexing and Downloading.

## Requirements

Requires Python 3.7 or greater. Personally I used Python 3.10.

You may install via:  
`pip install -r requirements.txt`

or install it manually by:  
`pip install tqdm aiohttp aiofiles orjson PyYAML`

## Usage

Figure it out yourself. Should be rather simple though:

1. Set your fantia cookie, set the users you want to scrape.
2. Rename the `Config.sample.yaml` to just `Config.yaml`. Remove the `.sample` would do.
3. Install required dependencies.
4. Run `Indexer.py`
5. Run `Downloader.py`
6. See your results in `work-path` specified in the YAML config.

## Other notes

- The script does script page and attempts to convert to Markdown. But it does not do style text as of now. I do eventually want to relook at it. But for now it works.

## License

As you can tell from the side, it's LGPL 3.0.