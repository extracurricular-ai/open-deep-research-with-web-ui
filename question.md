name:
“请提供[地点名称]的官方全称。”
“这个景点的常用名称是什么？”
slug:
“为[地点名称]生成一个简洁、小写、用连字符连接的URL友好slug。”
“请问[地点名称]的slug应该是什么？”
description:
“用500-1000字详细描述[地点名称]，包括其历史、文化意义、主要特色、吸引力以及为什么值得游览。”
“请为[地点名称]撰写一篇引人入胜的概述，突出其独特之处。”
“[地点名称]最吸引人的地方是什么？请详细说明。”
imageUUIDs:
“列出与[地点名称]相关的关键视觉元素（例如，地标建筑、特色景观、活动场景）的图片UUID。请确保这些图片能全面展示该地点的魅力。”
“请提供[地点名称]的代表性图片的UUID，至少包含5张。”
location:
“提供[地点名称]的地理位置信息，包括经度（longitude）和纬度（latitude）。”
“[地点名称]位于哪个城市、国家？请提供其精确的地理坐标。”
openingInfoString:
“请用标准OSM格式提供[地点名称]的开放时间信息。例如：'Mo-Fr 09:00-17:00; Sa-Su 10:00-16:00' 或 '24/7'。”
“[地点名称]的开放时间是怎样的？请提供详细的开放时间字符串。”
推荐路线 (Recommended Route):

RecommendedRoute:
“为[地点名称]设计一条推荐游览路线。请提供以下信息：”
“slug: 路线的URL友好slug。”
“title: 路线的标题，例如“[地点名称]一日游精华路线”。”
“description: 详细描述这条路线的亮点、体验和适合人群。”
“imageUUIDs: 路线相关的图片UUID。”
“duration: 路线的推荐游览时长（分钟）。”
“startLocation: 路线的起始地理位置（经纬度）。”
“endLocation: 路线的结束地理位置（经纬度）。”
“tags: 描述路线特点的标签系统，例如“历史”、“文化”、“自然”、“亲子”等。”
“type: 路线类型（'short'，'medium'，'long'）。”
“customContentBlocks: 路线中的定制内容块，包括标题、具体内容和相关图片UUID。”
实用提示 (Tips):

Tips:
“为[地点名称]提供5-10条实用旅行小贴士。每条小贴士应包含一个简洁的标题和具体内容，例如交通、着装、避开人群、特色体验等。”
“游客在游览[地点名称]时需要注意哪些事项？请提供一些有用的建议。”
标签 (Tags):

tags:
“请为[地点名称]分配合适的标签，使用TagSystem格式，例如 { type: 'category', value: '历史遗迹' } 或 { type: 'activity', value: '徒步' }。标签应涵盖其类型、特色、适合的活动等。”
“[地点名称]的特点是什么？请列出相关的标签。”
最佳游览时间 (BestTimeToVisit):

bestTimeToVisit:
“描述[地点名称]的最佳游览时间，包括推荐的季节、月份以及具体理由（例如，天气、活动、人群等）。”
“什么季节或月份最适合游览[地点名称]？为什么？”
周边景点 (NearbyAttractions):

nearbyAttractions:
“列出[地点名称]附近的5个相关景点slug。这些景点应该与[地点名称]地理位置相近或主题相关。”
“[地点名称]附近有哪些值得一去的景点？请提供它们的slug。”
规划信息 (PlanningInfo):

planningInfo:
“提供[地点名称]的详细规划信息，包括：”
“transportation: 前往[地点名称]的主要交通方式，例如公共交通、自驾、打车等，并提供相关细节（例如，可达性、耗时、费用）。请使用Transportation枚举类型。”
“accommodation: [地点名称]周边的住宿概况，包括推荐的住宿区域（name, description, bestFor）。”
“dining: [地点名称]周边的餐饮概况，包括推荐的餐厅（name, type, description, priceRange）。”
“costs: 游览[地点名称]的预估费用，包括门票、交通、餐饮等，以及任何需要额外付费的项目。”
常见问题 (FAQs):

faqs:
“为[地点名称]创建5-10个常见问题及答案。问题应涵盖游客可能关心的方面，例如门票、开放时间、交通、特殊规定等。”
“关于[地点名称]，游客常问的问题有哪些？请提供详细的问答。”
评论 (Reviews):

reviews:
“为[地点名称]生成3-5条模拟用户评论。每条评论应包含评论内容、评分（1-5星）和评论时间。”
“请根据[地点名称]的特点，撰写一些真实的游客评论。”
关联文章引用 (ArticleReference):

articleReference:
“如果[地点名称]有相关的深度文章，请提供文章的引用信息：”
“contentUrl: 文章内容的URL，格式为 "/content/pois/{slug}"。”
“hasArticle: 指示是否存在相关文章。”
“duration: 路线游览时长（秒）。”
层级关系和相关景点 (Hierarchical and Related POIs):

parentPoiSlug:
“如果[地点名称]是某个更大景点的子景点，请提供其父景点的slug。”
“例如，如果故宫内的某个殿堂是一个POI，它的parentPoiSlug就是“forbidden-city”。”
relatedPoiSlugs:
“列出与[地点名称]主题相似或地理位置接近的其他相关景点的slug，但不包括nearbyAttractions中已列出的。”
“除了nearbyAttractions之外，还有哪些景点与[地点名称]有紧密联系？”
时间戳 (Timestamps):

createdAt:
“提供[地点名称]条目创建的时间戳（ISO 8601格式）。例如：'2023-10-26T10:00:00Z'。”
updatedAt:
“提供[地点名称]条目最后更新的时间戳（ISO 8601格式）。例如：'2023-10-26T15:30:00Z'。”

以上是我的schema 请帮我搜索 地点名称：上下九步行街 各个方面的内容