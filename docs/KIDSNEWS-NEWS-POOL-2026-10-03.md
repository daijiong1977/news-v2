# News 候选池修正

用户要求：Fun 不能进入 News；News 原文上限放宽到 2,000 英文词；重新抓 PBS。

1. SourceFirstEditor.originals 的 News 入口禁止 origin category=Fun；摘要排序与后续
写稿均复用该入口。Fun 内容不能为了凑五篇转入 News，包括 Fun 来源的公共事务科技。
News/Science 到其他栏的已有分类规则未改。
2. News 原文范围 350–2000。Science 350–1500、Fun 180–1200 不变。
新采集 journal routing_max_words=2000；最终按目标栏目长度范围筛选，生成稿字数不变。
3. 新 News 采集在正文/图片抓取前应用已有明确元数据禁选门槛，并补齐
failed execution、明确恐袭准备及斧头攻击机组的表述；不因此拒绝一般法院、政策报道。
明确禁选稿不计入四篇合格，仍每源最多12条，六条全失败的暂停规则不变。
旧采集 journal 没有新标记时保留原抓取上限和早期筛选方式，不重写旧答卷。
4. PBS重抓在独立临时目录，抓RSS、正文、WebP并检查压缩后≥20,000字节；
不调用模型、不改旧运行、网站、数据库、archive 或 main。

测试：pipeline/test_news_pool_boundaries.py 三项修改前失败，修改后通过。
相关 Python3.10 套件46项通过。代码经既有PR86/PR1交付，未合并生产main。
