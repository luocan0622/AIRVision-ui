# AIRVision 自动化测试框架

基于 Python + pywinauto + pytest 的 Windows 桌面应用自动化测试框架，专为 AIRVision 应用设计。

> 完整项目说明请参阅 **[项目说明.md](项目说明.md)**（架构、配置、业务流程、测试体系、故障排查）。

## 项目结构

```
airvision_pyauto/
├── config/              # 配置文件
│   └── config.yaml      # 应用配置（路径、超时等）
├── pages/               # 页面对象模型
│   ├── base_page.py     # 基础页面类
│   ├── file_dialog.py   # 文件对话框 Mixin
│   ├── main_page.py     # 主窗口页面
│   └── dialogs.py       # 对话框标题常量
├── tests/               # 测试用例
│   ├── conftest.py      # pytest fixtures
│   ├── test_main_page.py       # 单步功能测试
│   ├── test_full_page.py       # 流程化测试
│   ├── test_full_workflow.py   # 完整 E2E 测试
│   └── test_sample.py          # 示例测试
├── utils/               # 工具模块
│   ├── app_manager.py   # 应用生命周期管理
│   ├── config.py        # 配置加载
│   ├── naming.py        # test_数字 命名
│   ├── ui_input.py      # 鼠标/键盘模拟
│   ├── logger.py        # 日志配置
│   └── screenshot.py    # 截图工具
├── logs/                # 日志输出目录
├── screenshots/         # 截图输出目录
├── reports/             # 测试报告目录
├── 项目说明.md           # 完整项目说明文档
├── requirements.txt
├── pytest.ini
└── README.md
```

## 环境要求

- Python 3.8+
- Windows 10/11
- AIRVision 应用

## 安装

1. 克隆项目：
```bash
git clone <repository-url>
cd airvision_pyauto
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
venv\Scripts\activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

编辑 `config/config.yaml` 配置文件：

```yaml
app:
  path: "C:/path/to/AIRVisionApp.exe"  # 应用路径
  title: "MainWindow"                   # 主窗口标题
  backend: "uia"                        # 后端：uia 或 win32
  timeout: 10                           # 超时时间（秒）
  close_on_finish: false                # 测试结束后是否关闭应用
```

## 运行测试

### 运行所有测试
```bash
pytest
```

### 运行特定标记的测试
```bash
# 冒烟测试
pytest -m smoke

# 回归测试
pytest -m regression

# 慢速测试
pytest -m slow
```

### 运行特定测试文件
```bash
pytest tests/test_main_page.py
```

### 运行特定测试用例
```bash
pytest tests/test_main_page.py::TestMainPageMenuBar::test_title_text
```

### 生成 HTML 报告
```bash
pytest --html=reports/report.html --self-contained-html
```

### 生成 Allure 报告
```bash
pytest --alluredir=reports/allure-results
allure serve reports/allure-results
```

## 测试标记

- `@pytest.mark.smoke` - 冒烟测试，验证核心功能
- `@pytest.mark.regression` - 回归测试，验证已有功能
- `@pytest.mark.slow` - 耗时较长的测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.unit` - 单元测试

## 页面对象模式

项目采用 Page Object Model (POM) 设计模式：

```python
from pages.main_page import MainPage

def test_example(app):
    page = MainPage(app)
    page.click_projects()
    page.new_project()
```

## 日志和截图

- **日志**：自动保存到 `logs/` 目录，按日期轮转
- **截图**：测试失败时自动截图，保存到 `screenshots/` 目录

## 开发指南

### 添加新的页面对象

1. 在 `pages/` 目录创建新文件
2. 继承 `BasePage` 类
3. 定义控件定位器和操作方法

```python
from pages.base_page import BasePage

class NewPage(BasePage):
    BTN_EXAMPLE = {"auto_id": "example_id", "control_type": "Button"}
    
    def click_example(self):
        self.click(**self.BTN_EXAMPLE)
```

### 添加新的测试用例

1. 在 `tests/` 目录创建测试文件
2. 使用 `app` fixture 获取应用实例
3. 添加适当的测试标记

```python
import pytest
from pages.main_page import MainPage

class TestNewFeature:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
    
    @pytest.mark.smoke
    def test_new_feature(self):
        # 测试代码
        pass
```

## 注意事项

1. **应用状态**：测试会检测应用是否已运行，避免重复启动
2. **窗口焦点**：某些操作需要窗口获得焦点才能正常执行
3. **等待时间**：根据应用响应速度调整 `config.yaml` 中的超时配置
4. **文件路径**：测试中使用的文件路径需要提前创建

## 故障排查

### 应用无法启动
- 检查 `config.yaml` 中的应用路径是否正确
- 确认应用可以手动正常启动

### 元素定位失败
- 使用 Inspect.exe 工具检查控件属性
- 调整超时时间或重试间隔
- 检查窗口是否获得焦点

### 测试不稳定
- 增加操作之间的等待时间
- 检查是否有异步操作未完成
- 查看日志文件定位问题

## 许可证

[添加许可证信息]

## 联系方式

[添加联系方式]