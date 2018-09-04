import os
import numpy as np
import pandas as pd
from collections import defaultdict
import re
import codecs
from itertools import combinations

def cut_sent(para):                     # 怎么样设定句号后有无"的条件，并且替换时又不包括第二个字符，这真是个神坑
    para = re.sub('([。！？?])([^”])',r"\1\n\2",para)
    para = re.sub('(\.{6})([^”])',r"\1\n\2",para)
    para = re.sub('(”)','”\n',para)
    para = para.rstrip()                     # 段尾如果有多余的\n就去掉它
    #很多规则中会考虑分号;，但是这里我把它忽略不计，破折号同样忽略
    return para.split("\n")

def build_trie(new_word,entity,trie_root):
    trie_node = trie_root
    for ch in new_word:
        if not ch in trie_node:
            trie_node[ch] = {}
        trie_node = trie_node[ch]
    if not 'leaf' in trie_node:
        trie_node['leaf'] = {entity}
    else:
        trie_node['leaf'].add(entity)

def dig_trie(sent,l,trie_root):                                #返回实体右边界r,实体范围
    trie_node = trie_root
    for i in range(l,len(sent)):
        if sent[i] in trie_node:
            trie_node = trie_node[sent[i]]
        else:
            if "leaf" in trie_node:
                return i, trie_node["leaf"]
            else:
                return -1, set()                                 # -1表示未找到
    # 收尾
    if "leaf" in trie_node:
        return len(sent), trie_node["leaf"]
    else:
        return -1, set()                                 # -1表示未找到

name_data = pd.read_excel("./name_data.xlsx",index_col=0)
name_data = name_data.set_index("姓名")
name_data = name_data.fillna("")
name_data = name_data.drop(["文武","张苞[董卓]","张苞[东汉]"])                # 文武这个人名简直是bug，历史上也不出名，把它剔除吧。还有其他一些微调
famous_person = name_data[name_data["字"] != "无"].index.tolist()  # 认为有“字”记载的人是有头有脸的人物，作为消歧的依据

names_trie = {}
for entity0, line in name_data.iterrows():
#     for name0 in [line["姓"]+line["名"],line["字"]]:               # 因为一开始就靠“字”来识别的错误概率太高，所以只有有了阅读历史才使用它
#         if not name0 in ["无","None",""] and len(name0) > 1:
#             build_trie(name0,entity0,names_trie)
    name0  = line["姓"]+line["名"]
    if not name0 in ["无","None",""] and len(name0) > 1:            # 长度1的名字太容易混淆，不采纳
        build_trie(name0,entity0,names_trie)

latest_mention = dict()                         # 用历史信息帮助消歧
def choose_from(name0,entities,trie_root):
    if len(entities) == 1:
        ret = list(entities)[0]
        related = name_data.loc[ret]
        for name2 in [related["字"],related["姓"]+related["名"]]:
            if len(name2) > 1:                 # 长度1的名字太容易混淆，不采纳
                build_trie(name2,ret,trie_root)          # 一旦有了阅读历史，就可以把该人的字作为索引查找实体
                latest_mention[name2] = ret
        return ret
    else:
        if name0 in latest_mention:
            return latest_mention[name0]
        else:
            for entity0 in entities:                  # 认为更有名气的人可能是书中提到的人
                if entity0 in famous_person:
                    return entity0
            return np.random.choice(list(entities))   # 可能还有更高级的消歧方法，不过这里就不使用了

def entity_linking(sent,trie_root):
    ret = []
    l = 0
    while l < len(sent):
        r, entities = dig_trie(sent,l,trie_root)
        if r != -1:
            name0 = sent[l:r]
            ret.append(([l,r],choose_from(name0,entities,trie_root)))         # 字典树能根据键找到实体范围，选择则依然需要根据历史等优化
            l = r
        else:
            l += 1
    return ret

def get_link(para,names_trie):
    sents = cut_sent(para)
    people_set = [set() for i in range(len(sents))]
    links = []
    for i in range(len(sents)):
        people_set[i] = set([entity for range0,entity in entity_linking(sents[i],names_trie)])
    related_sents = 2
    for i in range(len(sents)-related_sents):
        related_people = set()
        for j in range(i,i+related_sents):
            related_people = related_people.union(people_set[j])
        for pair0 in combinations(list(related_people),2):
            links.append(pair0)
    return links

basedir = "./三国演义/"
link_counts = defaultdict(int)
for i in range(1,121):
    print(i)
    filename = "%d.txt" % i
    text = codecs.open(basedir+filename,"r","utf-8")
    for para in text:                                                     # 按行读取，这里就认为每个换行符分割一段
        para = re.sub(r"姓(\S)名(\S)",r"\1\2",para).rstrip()
        # print(para)
        for a,b in get_link(para, names_trie):
            link_counts[(a, b)] += 1
            link_counts[(b, a)] += 1

link_counts = pd.Series(link_counts)
link_counts.to_excel("./link_counts.xlsx")
print(link_counts.sort_values(ascending=False))
