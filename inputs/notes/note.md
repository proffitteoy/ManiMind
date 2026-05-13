# 辅助笔记：Acceptability Judgements via Examining the Topology of Attention Maps

## 1. 这篇论文一句话讲什么

这篇论文的核心问题是：

**Transformer 的 attention map 不只是可视化热力图，它可以被看成一个带权图；这个图的拓扑结构能够反映句子的语法可接受性。**

作者把每个 attention head 的注意力矩阵转成图，再用 TDA 提取拓扑特征，例如连通分支、环、一维 barcode、H0M、RTD 等，用这些特征做两件事：

第一，判断一个句子是否语法可接受。

第二，在最小对立句对中判断哪一句更可接受。

论文声称，TDA 特征可以提升多语言 CoLA 类任务上的可接受性分类表现，并且在 BLIMP 最小对立句对任务上达到接近人类水平的表现；同时，这些拓扑特征还能帮助解释 attention head 对不同语法现象的作用。

---

## 2. 背景引子怎么讲

建议不要一上来讲 TDA，也不要一上来讲 persistent homology。先从“注意力机制到底有没有学到语言结构”切入。

可以这样讲：

> Transformer 的 attention map 经常被拿来解释模型在看什么。一个句子输入 BERT 后，每个 attention head 都会给出 token 与 token 之间的注意力关系。过去很多工作会直接观察某个 head 是否关注主语、宾语、标点、[CLS]、[SEP] 或相邻词。但问题是，attention map 本身是一个复杂的矩阵，仅仅看局部权重，很难判断它是否编码了更整体的语法结构。

然后引出语言学任务：

> 语言学里有一个经典问题叫 acceptability judgement，即判断一句话是否在语法上可接受。例如 “What did Betsy paint a picture of?” 是可接受的，而 “Maryann should leaving.” 不可接受。另一种更严格的形式是 minimal pair，即两句话只差一个局部语法现象，要求模型判断哪一句更自然。

再引出本文的思想：

> 如果 attention map 确实编码了句法关系，那么可接受句和不可接受句的 attention graph 结构应该不同。问题就变成：我们能不能用数学工具描述这种结构差异？本文的答案是：可以，把 attention map 看成带权图，然后用拓扑数据分析提取其持久结构。

论文在引言里明确把 linguistic acceptability 作为核心背景：可接受性判断长期是生成语言学的经验基础，常见形式包括二分类判断和最小对立句对；作者将 TDA 用于分析 attention heads 在语言可接受性中的作用。

---

## 3. 重点标注

### 重点 1：attention map 被转化为 weighted graph

原始对象不是文本本身，而是 Transformer attention matrix。

设 attention matrix 为：

[
A^{attn}
]

论文把它看成一个带权图：

[
G=(V,E,w)
]

其中：

* 顶点是 token；
* 边表示 token 之间的 mutual attention；
* 边权来自 attention weight；
* 每个 attention head 都可以产生一个 attention graph。

这是全文的建模起点。

第 3 页图 1 很关键：它展示了同一个句子 “There is snowing today.” 在不同 attention head 下形成不同 attention map、filtration 和 barcode。一个 head 更像链式结构，另一个 head 更像围绕 [SEP] 的星形结构。

---

### 重点 2：filtration 是“逐步删边/保边”观察图结构变化

论文不是只看一个固定图，而是通过 attention weight threshold 生成一族图：

[
G_{\tau_1},G_{\tau_2},\dots,G_{\tau_m}
]

随着阈值变化，边会被过滤掉，图的结构发生变化，例如：

* 连通分支数量变化；
* 环出现或消失；
* 最大生成树结构变化；
* 图从稠密变稀疏。

这就是 persistent homology 能介入的地方。

可以这样解释：

> attention map 不是静态热力图，而是一座“关系网络”。随着我们不断提高注意力阈值，弱关系被删掉，只剩下更强的 token-token 连接。TDA 关心的是：哪些结构在这个过程中稳定存在，哪些结构只是噪声。

---

### 重点 3：barcode 记录拓扑特征的 birth 和 death

论文使用 persistent homology 的语言：

* birth：某个拓扑特征出现；
* death：某个拓扑特征消失；
* lifetime：death - birth；
* barcode：这些 lifetime 的集合。

在 attention graph 中：

* (H_0) 主要对应连通分支；
* (H_1) 对应非平凡环；
* 黄色 bar 对应 0 维特征；
* 蓝色 bar 对应 1 维环结构。

第 3 页图 1 右侧就是 attention graph filtration 对应的 barcode，可用于 ManiMind 的重点动画场景。

---

### 重点 4：H0S 和 H0M 是最重要的简单特征

论文里最值得抓住的是 H0S/H0M。

H0S 表示 0 维 barcode 的 bar length 总和，等价地，它对应某个距离矩阵上的最小生成树边权总和。

H0M 是 H0S 的平均版本，可以理解为：

[
H0M = 1 - \text{attention graph 最大生成树的平均边权}
]

直观解释：

> H0M 衡量的是 attention graph 的骨架连接强度。如果一个句子的 attention graph 在强边层面更容易连成稳定结构，它的 H0M 会表现出不同分布。

论文讨论部分明确指出，H0S 及其归一化版本 H0M 对二分类可接受性判断和最小对立句对判断都有效，可以作为 LA classifier 的输入，也可以作为 minimal pairs 的打分函数。

---

### 重点 5：RTD 用于比较两个句子的 attention graph 拓扑差异

RTD，全称 Representation Topology Divergence，用于比较两个带权图之间的拓扑差异。

这个部分用于 minimal pair 很自然，因为 minimal pair 本来就是成对比较：

[
S_a: \text{acceptable sentence}
]

[
S_b: \text{unacceptable sentence}
]

作者分别计算两个句子的 attention graph：

[
G_a,\quad G_b
]

然后比较：

[
RTD(G_a,G_b)
]

和

[
RTD(G_b,G_a)
]

论文的判别规则是：

[
S_a \text{ acceptable}
\iff
RTD(G_a,G_b) < RTD(G_b,G_a)
]

第 4 页图 2 是这篇论文里最适合动画化的图：它展示了 acceptable sentence 和 unacceptable sentence 的 attention-derived graph 如何在不同阈值下产生 RTD barcode，绿色边表示只出现在其中一个图中的边，橙色条表示拓扑差异的 lifetime。

---

## 4. 方法主线应该怎么讲

这篇论文的技术主线可以压缩成 7 步：

1. 输入句子；
2. 送入 BERT/RoBERTa/XLM-R；
3. 取每个 attention head 的 attention matrix；
4. 把 attention matrix 转成 weighted graph；
5. 对 weighted graph 做 filtration；
6. 提取 TDA 特征：Betti number、barcode statistics、H0M、RTD、pattern distance；
7. 用这些特征做 acceptability classification 或 minimal pair scoring。

适合 ManiMind 生成的流程图：

```text
Sentence
→ Transformer
→ Attention Matrix
→ Attention Graph
→ Filtration
→ Barcode / Persistent Features
→ Classifier or Pairwise Scorer
→ Acceptable / Unacceptable
```

---

## 5. 实验重点

### 5.1 Acceptability Classification

任务：给定一个句子，判断是否语法可接受。

数据集包括：

* English CoLA；
* Italian ItaCoLA；
* Swedish DaLAJ。

模型做法：

* 冻结或微调 Transformer；
* 从 attention map 提取 TDA 特征；
* 用 Logistic Regression 分类；
* 与 fine-tuned LM baseline 比较。

结果重点：

论文报告 TDA classifier 在三种语言上通常优于 baseline，MCC 提升幅度最高为 English 0.14、Italian 0.24、Swedish 0.08；H0M 单独也能提升 English 和 Italian 的表现，但完整 TDA 特征最好。

---

### 5.2 Linguistic Minimal Pairs

任务：给定一对只差一个语法现象的句子，判断哪一句更可接受。

例子：

```text
Whose hat should Tonya wear?
*Whose should Tonya wear hat?
```

数据集：BLIMP。

BLIMP 包含 67 种 pair types，每种 1000 对句子，覆盖 12 类语言现象，包括 morphology、syntax、semantics。论文用 BERT-base 和 RoBERTa-base 的 attention heads，分别用 H0M 和 RTD 作为 scoring function。

结果重点：

RoBERTa-base + RTD 的 Head Ensemble 整体 accuracy 达到 88.9%，与 human baseline 88.6% 接近；论文还显示 head ensemble 比 all heads 更有效，因为并不是所有 head 都对语法现象有贡献。

---

## 6. 这篇论文真正的创新点

第一，它不是直接用 BERT embedding 做分类，而是用 attention graph 的拓扑结构做分类。

第二，它不是只做性能提升，而是把 TDA 用作 interpretability tool。

第三，它把 linguistic acceptability 的两个标准范式都覆盖了：

* binary acceptability judgement；
* minimal pair forced choice。

第四，它说明某些语法现象可能不是由单个 token 或单个 attention weight 决定，而是由整个 attention graph 的结构决定。

第五，它把“attention head 是否有语言功能”这个问题，转化成了“该 head 的拓扑特征是否区分语法现象”。

---

## 7. 适合标出的论文金句

可以在笔记里重点标出下面这几句话的中文转述：

> attention map 可以被看成 token 之间的带权图。

> TDA 不是看单条边，而是看图结构在阈值变化下的稳定拓扑特征。

> 可接受句和不可接受句的 attention graph 可能具有不同的拓扑形态。

> H0M 这种简单的 0 维持久同调特征，已经能够为语言可接受性判断提供有效信号。

> RTD 适合 minimal pair，因为它直接比较两个句子的 attention graph 拓扑差异。

> 拓扑特征更擅长捕捉形态、句法和结构关系，但对词汇项、可选句法成分、抽象语义因素较弱。论文讨论部分明确指出了这一限制。

---

## 8. 最后有什么应用

这里要分成“论文已经做的应用”和“可以延伸的应用”。

### 8.1 论文中已经验证的应用

第一，语法可接受性分类。

输入一句话，判断它是否语法可接受。应用场景包括语法检测、语言模型评估、NLG 输出质量评估等。

第二，minimal pair 判断。

输入两句只差一个局部语法现象的句子，判断哪一句更符合语法。这可以用于测试语言模型是否真正捕捉了某类语法规则。

第三，attention head 解释。

通过观察哪些 head 的拓扑特征对特定语法现象有效，可以分析不同 attention head 是否承担某些语言功能。论文指出，高层 head 的平均顶点度、连通分支、边数、环数、current-token attention 等特征对主要语言特征贡献较大。

---

### 8.2 可以延伸的应用

第一，LLM 语法能力诊断。

可以不只看模型输出对不对，而是看模型内部 attention graph 是否形成了稳定的句法结构。这个方向比单纯 benchmark score 更有解释性。

第二，模型压缩与 head selection。

论文显示并不是所有 heads 都有用，选出的 9 到 59 个 heads 就能达到较好表现。这个思想可以用于 pruning、模型压缩、推理加速。

第三，文本生成后处理。

对 NLG、机器翻译、自动摘要生成的候选句子，可以用 H0M/RTD 作为额外打分信号，辅助过滤语法结构异常的输出。

第四，跨语言句法比较。

论文做了 English、Italian、Swedish，未来可以扩展到类型差异更大的语言，观察哪些拓扑特征具有跨语言稳定性，哪些特征依赖语言类型。

第五，AI 生成文本检测。

这篇论文与 Kushnareva 等人关于 artificial text detection 的工作有延续关系。attention map topology 可以作为检测机器生成文本、异常文本或伪自然文本的结构信号。

第六，可解释 NLP 工具。

相比直接说“模型认为这句话错了”，TDA 特征可以提供结构层面的解释：是 attention graph 的连通结构、环结构、MST 骨架，还是与特定 attention pattern 的距离发生了变化。

---

## 9. 应用时必须注意的限制

这篇论文不是万能方法。

第一，计算成本较高。所有拓扑特征都依赖 Transformer attention matrix，因此计算复杂度至少不低于生成 attention matrix 的成本；论文给出 attention matrix 相关复杂度为 (O(n^2d + nd^2))。

第二，RTD 需要两个图之间有 one-to-one vertex correspondence。也就是说，两个句子的 token 数或 sub-token 对齐不一致时，实际处理会麻烦。

第三，head selection 需要额外辅助数据。论文也承认，用 auxiliary labeled minimal pairs 选择最佳 head，这和完全无监督的 minimal pair benchmark 设定并不完全一致。

第四，拓扑特征更偏结构，不擅长词汇和抽象语义。论文讨论中明确说，lexical items、optional syntactic elements、abstract semantic factors 可能较难由 topology 推断。

---

## 10. 如果做 ManiMind 演示，建议的讲解结构

建议分成 6 段：

### 第一段：问题引入

标题：

```text
Attention map 里是否藏着语法结构？
```

讲法：

```text
Transformer 的 attention head 会在 token 之间建立关系。
如果一个句子语法正确，模型内部的 token 关系是否会形成某种更稳定的结构？
如果句子语法错误，这种结构是否会发生拓扑变化？
```

---

### 第二段：从矩阵到图

标题：

```text
把 attention map 看成 token 关系图
```

画面：

```text
attention heatmap
→ weighted graph
→ token as vertex
→ attention weight as edge
```

---

### 第三段：从图到 filtration

标题：

```text
改变阈值，观察图的结构如何变化
```

画面：

```text
low threshold: dense graph
middle threshold: partial graph
high threshold: skeleton graph
```

重点：

```text
TDA 关注的不是某一条边，而是结构在阈值变化中的稳定性。
```

---

### 第四段：barcode 和 H0M

标题：

```text
稳定存在的连接结构可以被编码成 barcode
```

重点讲：

```text
H0 记录连通分支如何合并；
H1 记录环结构；
H0M 是一个简单但有效的 attention graph 结构指标。
```

---

### 第五段：minimal pair 和 RTD

标题：

```text
比较两句话的拓扑差异
```

用例子：

```text
Cheryl had trained Tara.
*Cheryl had murmured Tara.
```

讲法：

```text
两句话很相似，但一个可接受，一个不可接受。
RTD 比较它们的 attention graph 在 filtration 过程中的拓扑差异。
```

---

### 第六段：结果与应用

标题：

```text
拓扑特征不仅能提升性能，还能解释 head 的语言功能
```

结论：

```text
TDA 可以用于语法可接受性分类、minimal pair 判断、attention head 解释、模型诊断和生成文本质量评估。
```

---

## 11. 最适合让 ManiMind 生成的动画

1. attention heatmap 变成 weighted graph；
2. graph 随 threshold 变化，边逐渐消失；
3. 连通分支合并，对应 H0 barcode；
4. 环出现/消失，对应 H1 barcode；
5. acceptable/unacceptable 两个句子的 graph 对比；
6. RTD barcode 作为两个图之间的拓扑差异；
7. 最后显示分类器或 scorer 输出。

---

## 12. 最后一页总结可以这样写

```text
本文的核心思想是：

不要只把 attention map 看成一张热力图，
而要把它看成 token 之间的带权关系图。

当我们改变 attention threshold 时，
图的连通结构、环结构和骨架结构会发生变化。

这些变化可以通过 persistent homology、barcode、H0M 和 RTD 表示。

实验表明，
这些拓扑特征不仅能帮助判断句子是否语法可接受，
还能用于 minimal pair 判断，
并为解释 attention head 的语言功能提供结构化证据。
```

我的判断：这篇论文最适合你用来测试 ManiMind 的“论文理解 + 数学动画 + HTML 结构化解释”链路，因为它有清楚的图示对象、明确的数学转换、可量化实验结果和应用讨论。重点不是把所有 NLP 细节讲全，而是讲清楚这条主线：

```text
attention matrix
→ weighted graph
→ filtration
→ persistent features
→ acceptability judgement
```
