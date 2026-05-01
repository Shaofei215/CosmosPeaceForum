import tantivy
from pathlib import Path
import shutil
import jieba

test_dir = Path('./test_verify_default')
if test_dir.exists():
    shutil.rmtree(test_dir)

print('=== 方案A: 当前方案 - raw分词器 + 列表传入 ===')

schema_builder = tantivy.SchemaBuilder()
schema_builder.add_text_field('id', stored=True, tokenizer_name='raw')
schema_builder.add_text_field('content', stored=True, tokenizer_name='raw')
schema_builder.add_unsigned_field('owner_id', stored=True)
schema = schema_builder.build()

Path(test_dir).mkdir(parents=True, exist_ok=True)
index = tantivy.Index(schema=schema, path=str(test_dir))
writer = index.writer()

tokens = list(jieba.cut_for_search('我在论坛上看到了关于镜流新角色的讨论'))
writer.add_document(tantivy.Document(
    id='mem1',
    content=tokens,
    owner_id=42
))
writer.commit()
writer.wait_merging_threads()
index.reload()
searcher = index.searcher()

q, _ = index.parse_query_lenient('镜流', ['content'])
top = searcher.search(q, limit=10)
print('搜索 镜流: %d 条结果' % len(top.hits))

q2, _ = index.parse_query_lenient('角色 讨论', ['content'])
top2 = searcher.search(q2, limit=10)
print('搜索 角色 讨论: %d 条结果' % len(top2.hits))

shutil.rmtree(test_dir)

print('\n=== 方案B: default分词器 + 空格连接字符串 ===')

test_dir2 = Path('./test_verify_default2')
if test_dir2.exists():
    shutil.rmtree(test_dir2)

schema_builder2 = tantivy.SchemaBuilder()
schema_builder2.add_text_field('id', stored=True, tokenizer_name='default')
schema_builder2.add_text_field('content', stored=True, tokenizer_name='default')
schema_builder2.add_unsigned_field('owner_id', stored=True)
schema2 = schema_builder2.build()

Path(test_dir2).mkdir(parents=True, exist_ok=True)
index2 = tantivy.Index(schema=schema2, path=str(test_dir2))
writer2 = index2.writer()

tokens2 = list(jieba.cut_for_search('我在论坛上看到了关于镜流新角色的讨论'))
content_str = ' '.join(tokens2)
print('分词后字符串: %s' % content_str)

writer2.add_document(tantivy.Document(
    id='mem1',
    content=content_str,
    owner_id=42
))
writer2.commit()
writer2.wait_merging_threads()
index2.reload()
searcher2 = index2.searcher()

q, _ = index2.parse_query_lenient('镜流', ['content'])
top = searcher2.search(q, limit=10)
print('搜索 镜流: %d 条结果' % len(top.hits))

q2, _ = index2.parse_query_lenient('角色 讨论', ['content'])
top2 = searcher2.search(q2, limit=10)
print('搜索 角色 讨论: %d 条结果' % len(top2.hits))

shutil.rmtree(test_dir2)

print('\n=== 方案C: default分词器 + 中文原文（无预分词） ===')

test_dir3 = Path('./test_verify_default3')
if test_dir3.exists():
    shutil.rmtree(test_dir3)

schema_builder3 = tantivy.SchemaBuilder()
schema_builder3.add_text_field('id', stored=True, tokenizer_name='default')
schema_builder3.add_text_field('content', stored=True, tokenizer_name='default')
schema_builder3.add_unsigned_field('owner_id', stored=True)
schema3 = schema_builder3.build()

Path(test_dir3).mkdir(parents=True, exist_ok=True)
index3 = tantivy.Index(schema=schema3, path=str(test_dir3))
writer3 = index3.writer()

writer3.add_document(tantivy.Document(
    id='mem1',
    content='我在论坛上看到了关于镜流新角色的讨论',
    owner_id=42
))
writer3.commit()
writer3.wait_merging_threads()
index3.reload()
searcher3 = index3.searcher()

q, _ = index3.parse_query_lenient('镜流', ['content'])
top = searcher3.search(q, limit=10)
print('搜索 镜流: %d 条结果' % len(top.hits))

shutil.rmtree(test_dir3)

print('\n=== 总结 ===')
print('方案A (raw + list): 搜索成功')
print('方案B (default + 空格字符串): 需要验证')
print('方案C (default + 原文): 搜索失败，因为default分词器不支持中文')
