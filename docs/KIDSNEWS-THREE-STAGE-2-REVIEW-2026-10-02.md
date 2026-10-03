# Three-stage-2 成品与 DeepSeek 修复复核

2026-10-02。日志基线 cfb418c49d3d424d3eb8a8fb9cafa5929c099d42；
运行 work/2026-10-02/three-stage-2，CI 37052662036。
本次只读日志及站点，修改功能分支；没有重发布、写数据库/archive或邮件。

## 已核对的证据

- 三栏中文公开 payload 均 HTTP 200，逐字节哈希与日志 site 副本一致。
- 7次HTTP：News排序1、Science排序2（首答ID尾字误写）、Fun排序1；
  三栏写稿各1。总31318输入、51060输出、82378 tokens。
- 四次排序：News 13634 total/10143 reasoning；Science 6963/3656及
  8912/5245；Fun 8409/5380。合计24424 reasoning；排序可见输出1155。
- 三次写稿：News13958、Science16572、Fun13930 total，均stop、16K、
  thinking disabled、JSON mode。并非1M上下文不足或输出截断。
- 两个原始答卷的每行先关闭article，再放zh，最后多关闭一次对象。
  原始answer保留，离线恢复五行后两栏都通过validate_priority_batch；News不需恢复。
- 图片、字数、schema通过机械校验不代表事实、适龄或选题必然好；
  本轮没有视觉/手机端、全部详情语义或独立事实完整审查。

## 内容发现

1. News首篇刚果埃博拉以4018人死亡、无已知治疗/疫苗为中心，还写烧营地、
   医护死亡等；Easy题目考死亡人数。来源包含这些数字，但重要性不等于
   儿童意义。这不是要把所有国际新闻或疾病科学屏蔽，而是不能靠死亡数量占首位。
2. 法国教育稿有教育关联，但暴力、逮捕、纵火和催泪瓦斯占比过高。
   下一轮应突出学校服务/教育问题和经核实的应对，避免暴力数字主导。
3. NASA稿基于9月30日来源对10月1日的计划，10月2日发布。英文使用过去计划
   限定，不能称为验证已成功发射；中文目标时间也应明确是来源当时的计划。
4. Science最终是APOE4、鲨鱼、蟒蛇，全是生物相关；两家独立出版方已达标。
   APOE4研究基于小鼠/脑组织模型，三个语言版本须保留非已证实人体疗法限定。
5. Fun梅西动画和机械手有明确儿童兴趣；草莓织物偏应用科学，趣味排序仍可改善。
6. BBC Swimming/Tennis在本轮collection是pending、0尝试：达到前三源数量就停，
   并非模型看过体育候选后拒绝。Science较多ScienceDaily也受采集范围限制。
   已同意的Science/Fun每源3→3、每栏10篇仍是后续独立采集补丁，本轮未假称完成。

## 本补丁实现

- rank-shortlist HTTP 显式thinking disabled、JSON object、4096输出、temperature0.2。
  原生及其他任务不变。基于历史reasoning的节省不等于新轮实测用量保证。
- Python narrow decoder：只去字符串外可证明多余的对象结束括号，移同一行的
  sibling zh回article；不插正文、数字、逗号或缺失结构，不改原始answer。
  重复键、两份zh冲突、截断或其他歧义仍走原有限格式修复，不整组重发。
  batch-format-recovery.json记录原文hash及操作，完整内容仍走原校验。
- 五稿prompt不输出body_words/summary_chars，多强调zh层级；ID必须逐字复制。
- 影子News排序前排除“疫情＋死亡数字主导”标题，并记录shortlist-exclusions。
  排序/写稿/Grok成品共用儿童受众规则：适合且有意义优先，再比重要性；
  国际新闻须有清晰学习/实际意义，不能凭空添加关联或用卫生常识洗白不合适选题。
- 补充研究模型、中文限定和旧计划日期规则；词数15%容差、安全/历史/hash不变。
- 不修改full_round/news_rss_core/wordcount_policy等旧生产行为。

参考：DeepSeek官方说明thinking默认enabled/high，JSON mode需response_format及示例：
https://api-docs.deepseek.com/guides/thinking_mode/ ，
https://api-docs.deepseek.com/guides/json_mode/ 。

## 运行边界

共享源码Python3.10相关离线套件274项通过（两个已有警告）。回归覆盖排序参数、
News付费排序前排除、非误杀疫苗稿、格式歧义/截断拒绝、真实文件provider恢复路径。
缓存本轮三栏原答卷离线复核均通过批次验证；不增加任何真实模型调用。

新prompt改变request hash：下一轮新目录使用，不编辑已接受/已发布的冻结输入和答卷。
现有网站这一轮不自动替换。要撤换已发布内容需另行授权和按既有发布/回滚流程。
