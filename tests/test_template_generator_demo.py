from automation.template_generator import TemplateGenerator, detect_and_generate_prompt
from automation.config import config

print('=== 模板生成器测试 ===\n')

generator = TemplateGenerator()

print(f"支持的模板类型: {generator.get_all_types()}\n")

test_cases = [
    {
        'title': 'Python编程实战 - 从入门到精通',
        'author': '张三',
        'description': '本书是一本Python实战教程，包含大量代码示例和项目实战'
    },
    {
        'title': '深度工作: 如何有效使用每一点脑力',
        'author': '卡尔·纽波特',
        'description': '本书提供了关于深度工作的原则和实践方法'
    },
    {
        'title': '重新定义公司: 谷歌是如何运营的',
        'author': '埃里克·施密特',
        'description': '通过大量谷歌的案例，论证了创意型组织的运营之道'
    },
    {
        'title': '刻意练习: 如何从新手到大师',
        'author': '安德斯·艾利克森',
        'description': '讲述了一整套关于技能提升的心理学理论'
    },
    {
        'title': '追风筝的人',
        'author': '卡勒德·胡赛尼',
        'description': '一部感人至深的阿富汗小说'
    }
]

for i, book in enumerate(test_cases, 1):
    print(f'--- 测试{i}: {book["title"]} ---')

    book_type = generator.detect_book_type(book)
    type_info = generator.get_type_info(book_type)

    print(f'检测类型: {type_info["name"]} ({book_type})')

    prompt = generator.generate_prompt(book, book_type)
    print(f'生成提示词长度: {len(prompt)} 字符')
    print(f'提示词前200字: {prompt[:200]}...')
    print()

print('=== 测试完成 ===')
