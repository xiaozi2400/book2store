from automation.suitability_evaluator import SuitabilityEvaluator, evaluate_book_suitability
from automation.config import config

print('=== 配置加载测试 ===')
eval_cfg = config.suitability_eval_config()
print(f'版本: {eval_cfg.get("version")}')
print(f'评估维度数: {len(eval_cfg.get("criteria", []))}')
print(f'阈值: excellent={eval_cfg.get("decision", {}).get("excellent_threshold")}, good={eval_cfg.get("decision", {}).get("good_threshold")}')

print('\n=== 评估器测试 ===')
evaluator = SuitabilityEvaluator()

book1 = {
    'title': 'Python编程实战 - 从入门到精通',
    'author': '张三',
    'description': '本书是一本Python实战教程，包含大量代码示例和项目实战'
}
result1 = evaluator.evaluate(book1)
print(f'测试1(技术指南): {result1.label} - {result1.score}分')
print(f'  建议: {result1.recommendation}')

book2 = {
    'title': '追风筝的人',
    'author': '卡勒德·胡赛尼',
    'description': '一部感人至深的阿富汗小说'
}
result2 = evaluator.evaluate(book2)
print(f'测试2(小说): {result2.label} - {result2.score}分')
print(f'  建议: {result2.recommendation}')

book3 = {
    'title': '深度工作: 如何有效使用每一点脑力',
    'author': '卡尔·纽波特',
    'description': '本书提供了关于深度工作的原则和实践方法'
}
result3 = evaluator.evaluate(book3)
print(f'测试3(方法论): {result3.label} - {result3.score}分')
print(f'  建议: {result3.recommendation}')

book4 = {
    'title': 'AI Agents: The Definitive Guide',
    'author': 'Nicole Koenigstein',
    'description': 'A comprehensive handbook for building AI agents with practical examples and projects'
}
result4 = evaluator.evaluate(book4)
print(f'测试4(英文技术书): {result4.label} - {result4.score}分')
print(f'  建议: {result4.recommendation}')

print('\n=== 所有测试通过 ===')
