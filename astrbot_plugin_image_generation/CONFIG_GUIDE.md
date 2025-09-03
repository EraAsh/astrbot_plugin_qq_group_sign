AstrBot Image Generation Plugin Configuration Guide

目的
- 通过 siliconeflow API 自动生成图片。该插件使用 AstrBot 的配置系统来加载 API 设置。

依赖与环境
- Python 3.x
- aiohttp>=3.8.0
- regex

相关文件与示例
- example_config.json：提供一个可直接使用的模板配置，便于在 UI 中快速加载默认值。

配置字段（来源于 _conf_schema.json）
- siliconflow.api_key
  - 描述：硅基流动API密钥
  - 类型：string
  - 是否必填：是
  - 获取方式：从 https://cloud.siliconflow.cn/ 获取
- siliconflow.api_url
  - 描述：硅基流动API地址
  - 类型：string
  - 默认值： https://api.siliconflow.cn/v1/images/generations
- siliconflow.model
  - 描述：生成图片使用的模型
  - 类型：string
  - 默认值： black-forest-labs/FLUX.1-schnell

示例配置（JSON）
{
  "siliconflow": {
    "api_key": "YOUR_API_KEY",
    "api_url": "https://api.siliconflow.cn/v1/images/generations",
    "model": "black-forest-labs/FLUX.1-schnell"
  }
}

如何在 AstrBot UI 设置
1) 将插件放入 AstrBot 的 data/plugins 目录并启用插件。
2) 在 AstrBot WebUI 的插件管理页面，选择 astrbot_plugin_image_generation，点击配置。
3) 在出现的字段中填入：
   - API Key（siliconflow.api_key）
   - API URL（siliconflow.api_url，若使用默认值可留空）
   - 模型名称（siliconflow.model，若使用默认值可留空）
4) 保存配置后，点击“重载插件”以应用新设置。

部署与测试
- 保存配置后，重载插件。
- 与插件的对话中发送包含绘图意图的自然语言描述（如“画一只猫”），插件应自动识别并调用硅基流动 API 生成图片，返回图片链接并展示图片。

注意事项
- 请勿在代码中硬编码 API 密钥，务必通过 UI 配置。
- 如遇网络错误或 API 限流，插件实现了重试与速率控制逻辑，仍可能需要合理的 API 配额。
- 确保网络连通性以及 API 的可用性，确保证书等网络安全设置正确。
