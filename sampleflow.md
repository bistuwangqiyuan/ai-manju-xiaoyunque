<span id="q1ryhsv4"></span>
# 示例说明

本示例将使用小剧本《藏在奶茶里的戒指》，完整展示小云雀\-短剧漫剧Agent从剧本解析到单集视频合成的调用流程。本示例选用的视频生成模型为「Seedance 2.0 720p」。

<Attachment link="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_f5cb869e0e013ba4cc6f14f8dae23f1d.docx" name="藏在奶茶里的戒指.docx">藏在奶茶里的戒指.docx</Attachment>


<span id="2cSGIbVT"></span>
# 剧本解析

> 接口详细说明请阅读[「小云雀-短剧漫剧Agent-剧本解析-接口文档」](https://www.volcengine.com/docs/85621/2389851?lang=zh)


<span id="1EBJlHsl"></span>
## 提交任务

<span id="Jttah5MJ"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_script_analysis",
    "visual_style": "真人写实, 电影风格, 冷色调",
    "video_ratio": "16:9",
    "file_url": "https://xxxx/藏在奶茶里的戒指.docx",
    "file_type": "docx",
    "file_name": "藏在奶茶里的戒指.docx"
}
```


<span id="UL4xDSR5"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "task_id": "14158393146858488418"
    },
    "message": "Success",
    "request_id": "20260515130321F46E86E95FE26EF05812",
    "status": 10000,
    "time_elapsed": "273.30114ms"
}
```


<span id="rWIWWnpi"></span>
## 查询任务

<span id="2rWf1zgm"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_script_analysis",
    "task_id": "14158393146858488418"
}
```


<span id="0Bta9cPQ"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "aigc_meta_tagged": false,
        "resp_data": "{\"thread_id\":\"ark_3572523320385040940\",\"assets_id\":\"ark_1194097890828\",\"status\":\"Success\",\"script_detail\":{\"OverviewAssetID\":\"1194097890828\",\"ScriptAssetID\":\"1193704634124\",\"CoreElement\":{\"CoreSetting\":\"现代都市爱情求婚故事：陈屿与许知夏是两年前在奶茶店相识的恋人，两年前陈屿在公园向许知夏承诺买一辈子奶茶，两年后的夜晚陈屿在公园许愿池边正式向许知夏求婚\",\"Time\":\"现代都市，两年前至今\",\"MainCharacter\":\"陈屿\",\"Location\":\"街角奶茶店、城市公园步道、公园许愿池\",\"CorePlot\":\"陈屿在奶茶店紧张地等待许知夏，并准备用戒指求婚。许知夏到达后，两人回忆起他们第一次约会时，陈屿就在这里为她点了同款奶茶。\\n许知夏和陈屿在公园步道散步，许知夏询问陈屿为何心事重重。陈屿提及两年前两人在此地许愿的往事，但最终未能鼓起勇气说出求婚的话，只是在心中暗下决心下次不再搞砸。\\n陈屿在许愿池边向许知夏惊喜求婚，他手持钻戒单膝跪地，深情告白。许知夏感动落泪，欣然应允，陈屿为她戴上戒指并紧紧相拥。\\n\",\"Perspective\":\"主角视角第一人称\",\"Summary\":\"陈屿与许知夏相恋多年，这一天对他而言意义非凡。他早早来到两人初次约会的奶茶店，紧张地等待着女友的到来，手中紧握着那枚承载着承诺的戒指。当许知夏出现时，陈屿心中涌起复杂的情感，两人相视而笑，仿佛回到了当年青涩的相识时刻，许知夏发现陈屿为她点的正是初次约会时的那款奶茶，熟悉的味道唤起了美好的回忆。随后，两人在公园步道悠然散步，初秋的微风轻拂，许知夏察觉到陈屿似乎心事重重。陈屿提及两年前两人曾在此许愿的往事，那时的他满怀憧憬却终究未能鼓起勇气说出那句求婚的话，他暗暗发誓这次绝不再搞砸。在许愿池边，陈屿终于下定决心，他单膝跪地，郑重地取出钻戒，深情告白，倾诉着对许知夏的爱意与珍视。许知夏被这突如其来的惊喜感动得落泪，欣然应允了这份真挚的求婚，陈屿为她戴上戒指，两人紧紧相拥，终于迎来了属于他们的幸福时刻。多年等待与忐忑在这一刻化为圆满，陈屿用勇气与真心为这段爱情写下了最美好的承诺。\",\"Style\":\"搞笑\",\"Background\":\"现代都市爱情求婚故事：陈屿与许知夏是两年前在奶茶店相识的恋人，两年前陈屿在公园向许知夏承诺买一辈子奶茶，两年后的夜晚陈屿在公园许愿池边正式向许知夏求婚；地点：街角奶茶店、城市公园步道、公园许愿池；时间：现代都市，两年前至今\",\"EpisodeCount\":3,\"FrequencyCategory\":\"女频\"},\"Settings\":{\"VisualStyle\":\"真人写实, 电影风格, 冷色调\",\"VideoRatio\":\"16:9\"},\"CharacterAssets\":[{\"CharacterID\":\"C1\",\"CharacterName\":\"陈屿\",\"CharacterAssetID\":\"1193719571468\",\"AppearanceCount\":3,\"EpisodeAssetIDs\":[\"1193839593996\",\"1194108855308\",\"1194215545868\"],\"IsMainCharacter\":true},{\"CharacterID\":\"C2\",\"CharacterName\":\"许知夏\",\"CharacterAssetID\":\"1193911234060\",\"AppearanceCount\":3,\"EpisodeAssetIDs\":[\"1193839593996\",\"1194108855308\",\"1194215545868\"],\"Aliases\":[\"知夏\"]}],\"SceneAssets\":[{\"SceneAssetID\":\"1193827913740\",\"EpisodeAssetIDs\":[\"1193839593996\"]},{\"SceneAssetID\":\"1194108981004\",\"EpisodeAssetIDs\":[\"1194108855308\"]},{\"SceneAssetID\":\"1193993438988\",\"EpisodeAssetIDs\":[\"1194215545868\"]}],\"EpisodeAssets\":[{\"EpisodeID\":\"1\",\"EpisodeName\":\"1193704634124-001\",\"EpisodeTitle\":\"奶茶店里的求婚秘密\",\"EpisodeAssetID\":\"1194108855308\",\"StoryboardAssetID\":\"1194110367756\",\"CharacterAssetIDs\":[\"1193719571468\",\"1193911234060\"],\"SceneAssetIDs\":[\"1194108981004\"],\"EpisodeSynopsisAssetID\":\"1193839613452\"},{\"EpisodeID\":\"2\",\"EpisodeName\":\"1193704634124-002\",\"EpisodeTitle\":\"桂香夜语欲言又止\",\"EpisodeAssetID\":\"1193839593996\",\"StoryboardAssetID\":\"1194129613068\",\"CharacterAssetIDs\":[\"1193719571468\",\"1193911234060\"],\"SceneAssetIDs\":[\"1193827913740\"],\"EpisodeSynopsisAssetID\":\"1194129535244\"},{\"EpisodeID\":\"3\",\"EpisodeName\":\"1193704634124-003\",\"EpisodeTitle\":\"许愿池畔浪漫求婚\",\"EpisodeAssetID\":\"1194215545868\",\"StoryboardAssetID\":\"1194002046732\",\"CharacterAssetIDs\":[\"1193719571468\",\"1193911234060\"],\"SceneAssetIDs\":[\"1193993438988\"],\"EpisodeSynopsisAssetID\":\"1193984817420\"}],\"StoryboardBriefs\":[{\"EpisodeID\":\"1\",\"EpisodeAssetID\":\"1194108855308\",\"StoryboardAssetID\":\"1194110367756\"},{\"EpisodeID\":\"2\",\"EpisodeAssetID\":\"1193839593996\",\"StoryboardAssetID\":\"1194129613068\"},{\"EpisodeID\":\"3\",\"EpisodeAssetID\":\"1194215545868\",\"StoryboardAssetID\":\"1194002046732\"}],\"StageStatusMap\":{\"script_overview_analysis\":{\"Status\":3,\"Message\":\"剧本大纲分析成功\"},\"dynamic_form\":{\"Status\":3,\"Message\":\"表单填写成功\"}}},\"charge_count\":9}",
        "status": "done"
    },
    "message": "Success",
    "request_id": "20260515130726B0DEB99E99E48BF2E1AB",
    "status": 10000,
    "time_elapsed": "44.138458ms"
}
```


&nbsp;


<span id="jwnx88nI"></span>
### resp_data 反序列化结果展示

<div data-tips="true" data-tips-type="default" data-tips-is-title="true">说明</div>


<div data-tips="true" data-tips-type="default">请妥善保存接口返回的 assets_id（资产 ID）、thread_id（会话 ID）及 EpisodeID （剧集 ID），用于后续流程；</div>


```JSON
{
    "thread_id": "ark_3572523320385040940",
    "assets_id": "ark_1194097890828",
    "status": "Success",
    "script_detail": {
        "OverviewAssetID": "1194097890828",
        "ScriptAssetID": "1193704634124",
        "CoreElement": {
            "CoreSetting": "现代都市爱情求婚故事：陈屿与许知夏是两年前在奶茶店相识的恋人，两年前陈屿在公园向许知夏承诺买一辈子奶茶，两年后的夜晚陈屿在公园许愿池边正式向许知夏求婚",
            "Time": "现代都市，两年前至今",
            "MainCharacter": "陈屿",
            "Location": "街角奶茶店、城市公园步道、公园许愿池",
            "CorePlot": "陈屿在奶茶店紧张地等待许知夏，并准备用戒指求婚。许知夏到达后，两人回忆起他们第一次约会时，陈屿就在这里为她点了同款奶茶。\n许知夏和陈屿在公园步道散步，许知夏询问陈屿为何心事重重。陈屿提及两年前两人在此地许愿的往事，但最终未能鼓起勇气说出求婚的话，只是在心中暗下决心下次不再搞砸。\n陈屿在许愿池边向许知夏惊喜求婚，他手持钻戒单膝跪地，深情告白。许知夏感动落泪，欣然应允，陈屿为她戴上戒指并紧紧相拥。\n",
            "Perspective": "主角视角第一人称",
            "Summary": "陈屿与许知夏相恋多年，这一天对他而言意义非凡。他早早来到两人初次约会的奶茶店，紧张地等待着女友的到来，手中紧握着那枚承载着承诺的戒指。当许知夏出现时，陈屿心中涌起复杂的情感，两人相视而笑，仿佛回到了当年青涩的相识时刻，许知夏发现陈屿为她点的正是初次约会时的那款奶茶，熟悉的味道唤起了美好的回忆。随后，两人在公园步道悠然散步，初秋的微风轻拂，许知夏察觉到陈屿似乎心事重重。陈屿提及两年前两人曾在此许愿的往事，那时的他满怀憧憬却终究未能鼓起勇气说出那句求婚的话，他暗暗发誓这次绝不再搞砸。在许愿池边，陈屿终于下定决心，他单膝跪地，郑重地取出钻戒，深情告白，倾诉着对许知夏的爱意与珍视。许知夏被这突如其来的惊喜感动得落泪，欣然应允了这份真挚的求婚，陈屿为她戴上戒指，两人紧紧相拥，终于迎来了属于他们的幸福时刻。多年等待与忐忑在这一刻化为圆满，陈屿用勇气与真心为这段爱情写下了最美好的承诺。",
            "Style": "搞笑",
            "Background": "现代都市爱情求婚故事：陈屿与许知夏是两年前在奶茶店相识的恋人，两年前陈屿在公园向许知夏承诺买一辈子奶茶，两年后的夜晚陈屿在公园许愿池边正式向许知夏求婚；地点：街角奶茶店、城市公园步道、公园许愿池；时间：现代都市，两年前至今",
            "EpisodeCount": 3,
            "FrequencyCategory": "女频"
        },
        "Settings": {
            "VisualStyle": "真人写实, 电影风格, 冷色调",
            "VideoRatio": "16:9"
        },
        "CharacterAssets": [
            {
                "CharacterID": "C1",
                "CharacterName": "陈屿",
                "CharacterAssetID": "1193719571468",
                "AppearanceCount": 3,
                "EpisodeAssetIDs": [
                    "1193839593996",
                    "1194108855308",
                    "1194215545868"
                ],
                "IsMainCharacter": true
            },
            {
                "CharacterID": "C2",
                "CharacterName": "许知夏",
                "CharacterAssetID": "1193911234060",
                "AppearanceCount": 3,
                "EpisodeAssetIDs": [
                    "1193839593996",
                    "1194108855308",
                    "1194215545868"
                ],
                "Aliases": [
                    "知夏"
                ]
            }
        ],
        "SceneAssets": [
            {
                "SceneAssetID": "1193827913740",
                "EpisodeAssetIDs": [
                    "1193839593996"
                ]
            },
            {
                "SceneAssetID": "1194108981004",
                "EpisodeAssetIDs": [
                    "1194108855308"
                ]
            },
            {
                "SceneAssetID": "1193993438988",
                "EpisodeAssetIDs": [
                    "1194215545868"
                ]
            }
        ],
        "EpisodeAssets": [
            {
                "EpisodeID": "1",
                "EpisodeName": "1193704634124-001",
                "EpisodeTitle": "奶茶店里的求婚秘密",
                "EpisodeAssetID": "1194108855308",
                "StoryboardAssetID": "1194110367756",
                "CharacterAssetIDs": [
                    "1193719571468",
                    "1193911234060"
                ],
                "SceneAssetIDs": [
                    "1194108981004"
                ],
                "EpisodeSynopsisAssetID": "1193839613452"
            },
            {
                "EpisodeID": "2",
                "EpisodeName": "1193704634124-002",
                "EpisodeTitle": "桂香夜语欲言又止",
                "EpisodeAssetID": "1193839593996",
                "StoryboardAssetID": "1194129613068",
                "CharacterAssetIDs": [
                    "1193719571468",
                    "1193911234060"
                ],
                "SceneAssetIDs": [
                    "1193827913740"
                ],
                "EpisodeSynopsisAssetID": "1194129535244"
            },
            {
                "EpisodeID": "3",
                "EpisodeName": "1193704634124-003",
                "EpisodeTitle": "许愿池畔浪漫求婚",
                "EpisodeAssetID": "1194215545868",
                "StoryboardAssetID": "1194002046732",
                "CharacterAssetIDs": [
                    "1193719571468",
                    "1193911234060"
                ],
                "SceneAssetIDs": [
                    "1193993438988"
                ],
                "EpisodeSynopsisAssetID": "1193984817420"
            }
        ],
        "StoryboardBriefs": [
            {
                "EpisodeID": "1",
                "EpisodeAssetID": "1194108855308",
                "StoryboardAssetID": "1194110367756"
            },
            {
                "EpisodeID": "2",
                "EpisodeAssetID": "1193839593996",
                "StoryboardAssetID": "1194129613068"
            },
            {
                "EpisodeID": "3",
                "EpisodeAssetID": "1194215545868",
                "StoryboardAssetID": "1194002046732"
            }
        ],
        "StageStatusMap": {
            "script_overview_analysis": {
                "Status": 3,
                "Message": "剧本大纲分析成功"
            },
            "dynamic_form": {
                "Status": 3,
                "Message": "表单填写成功"
            }
        }
    },
    "charge_count": 9
}
```





<span id="y0CHdHwT"></span>
# 图片生成

> 接口详细说明请阅读[「小云雀-短剧漫剧Agent-图片生成-接口文档」](https://www.volcengine.com/docs/85621/2389852?lang=zh)


<span id="tgHhj1t6"></span>
## 提交任务

<span id="dQXzNCcN"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_material_design",
    "assets_id": "ark_1194097890828",  // 剧本解析返回的assets_id
    "thread_id": "ark_3572523320385040940",  // 剧本解析返回的thread_id
    "run_id": "example_design_1234"
}
```


<span id="NnrjV62I"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "task_id": "10835018322538893580"
    },
    "message": "Success",
    "request_id": "202605151308328675B22BF912E65F8A1D",
    "status": 10000,
    "time_elapsed": "63.779537ms"
}
```


<span id="Vc6pyjMy"></span>
## 查询任务

<span id="un7fHAVx"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_material_design",
    "task_id": "10835018322538893580"
}
```


<span id="wdnV5ehe"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "aigc_meta_tagged": false,
        "resp_data": "{\"thread_id\":\"ark_3572523320385040940\",\"assets_id\":\"ark_1194097890828\",\"status\":\"Success\",\"character_detail\":[{\"CharacterID\":\"C1\",\"CharacterName\":\"陈屿\",\"IsMainCharacter\":true,\"Introduction\":\"陈屿是一位深情且细心的都市青年，是许知夏的男友。他珍视与女友的感情，对两人相处的点滴细节记忆犹新，并精心策划了求婚。在关键时刻他会表现出紧张和犹豫，但最终能够鼓起勇气，用真诚坚定的态度表达爱意，成功向许知夏求婚，从男友转变为未婚夫。他的形象是当代浪漫关系中一个普通但真挚的男性代表。\",\"TagInfos\":[{\"Name\":\"基础形象\",\"Identity\":[\"许知夏的男友\",\"上班族\"],\"Personality\":\"深情专一、细心体贴、有仪式感、关键时刻会紧张犹豫、内在坚定\",\"Background\":\"生活在都市，与女友许知夏交往至少两年，两人有固定的约会地点（奶茶店）和充满回忆的场所（公园许愿池）。是一名上班族。\",\"Gender\":\"男\",\"AgeGroup\":\"青年\",\"VoiceInfo\":{\"Description\":\"男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中\"},\"AppearanceInfo\":{\"Description\":\"一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。\"},\"IsCore\":true}],\"AppearanceTree\":{\"NodeID\":\"346df3d0-b035-4057-9fd2-a519b9a8e4e0\",\"AssetID\":\"1193731783692\",\"Detail\":{\"NodeID\":\"\",\"Name\":\"陈屿\",\"StageName\":\"基础形象\",\"Label\":\"基础形象\",\"FullName\":\"陈屿-基础形象-基础形象\",\"IsRoot\":true,\"Appearance\":\"一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。\",\"VoiceInfo\":{\"Description\":\"男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中\"},\"BodyImageID\":\"7639981941240136217\",\"BustPortraitID\":\"7639981897310175769\",\"RelatedEpisodeNum\":[\"1\",\"2\",\"3\"],\"BodyImageURL\":\"https://everphoto-media.jianying.com/origin/7639981941240136217?X-Everphoto-Expires=1784006045&X-Everphoto-Sum=ac518e0a01bb277d617f5a4d21f87e6a68b9e500&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0ogTxYJ5eFx3RTA8X5Xr62WtXCw0fDXoIP8WgHtnMOOJhGuGtSw7uaGfmYJxH1hfE\",\"BustPortraitURL\":\"https://everphoto-media.jianying.com/origin/7639981897310175769?X-Everphoto-Expires=1784006045&X-Everphoto-Sum=7c5c79708961b2cb7b07083c26f473ef5cbc804a&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X2RyqEqW-LUS8MMuWoY8hicqAk8ZEtVJsHKFhdZHbapUbEaniKx32kQ2oEdGK4ahVU\"}},\"ExpectRenderImageCount\":1,\"ActualRenderImageCount\":1},{\"CharacterID\":\"C2\",\"CharacterName\":\"许知夏\",\"Alias\":[\"知夏\"],\"Introduction\":\"许知夏是男主角陈屿的女友，后成为其未婚妻。她是一个情感细腻、善于观察且略带俏皮的年轻女性。她珍视与陈屿的共同回忆，记得两人第一次约会的奶茶口味，同时也能够直接地表达自己的疑惑和情感。在陈屿的求婚下，她真情流露，欣然应允，开启了人生的新篇章。\",\"TagInfos\":[{\"Name\":\"基础形象\",\"Identity\":[\"陈屿的女友\",\"陈屿的未婚妻\"],\"Personality\":\"情感细腻、恋旧（记得初次约会的奶茶）、观察力敏锐（能察觉到陈屿的心事）、性格直率且带点俏皮（会直接询问，也会假装生气）。在关键时刻真情流露，毫不犹豫地表达爱意。\",\"Background\":\"与陈屿交往至少两年，两人第一次约会的地点是在一家街角奶茶店，感情稳定并最终接受了陈屿的求婚。\",\"Gender\":\"女\",\"AgeGroup\":\"青年\",\"VoiceInfo\":{\"Description\":\"女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中\"},\"AppearanceInfo\":{\"Description\":\"一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。\"},\"IsCore\":true}],\"AppearanceTree\":{\"NodeID\":\"82c4b0bc-c489-4eb2-957d-0bbee63e8cbd\",\"AssetID\":\"1194318554124\",\"Detail\":{\"NodeID\":\"\",\"Name\":\"许知夏\",\"StageName\":\"基础形象\",\"Label\":\"基础形象\",\"FullName\":\"许知夏-基础形象-基础形象\",\"IsRoot\":true,\"Appearance\":\"一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。\",\"VoiceInfo\":{\"Description\":\"女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中\"},\"BodyImageID\":\"7639981959057572377\",\"BustPortraitID\":\"7639981959057539609\",\"RelatedEpisodeNum\":[\"1\",\"2\",\"3\"],\"BodyImageURL\":\"https://everphoto-media.jianying.com/origin/7639981959057572377?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=5324486e26e39bc98e3f94bbb11e31f9c61906b9&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0PmApliUcle2A-Ns_4VCbbCJr1cObG-2SDxTTPkKsG_1znP8ScTru6sWxM3FymoSI\",\"BustPortraitURL\":\"https://everphoto-media.jianying.com/origin/7639981959057539609?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=7557531965b51e0d47f66e87848f2dde207f01dc&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0ZWDmzBVMmBXOQYYzz0EPmxS_Cx4Tx3YQHuUoJM3Qsd3kNIgAzntxs4RXt7pmMqDo\"}},\"ExpectRenderImageCount\":1,\"ActualRenderImageCount\":1}],\"scene_detail\":[{\"SceneID\":\"1193827913740\",\"Name\":\"城市公园步道\",\"AppearanceDetails\":[{\"AppearanceID\":\"1194314335244\",\"Description\":\"机位设置在公园步道的一侧，呈中景视角。夜晚，暖黄色的路灯沿着石板铺就的小径向前延伸，在地面投下柔和的光斑。步道两侧是茂盛的绿植和几株桂花树，枝叶在夜色中呈现深绿色轮廓。记忆点：在步道延伸方向的远处背景中，可以看到一座亮着灯的圆形许愿池，水面反射着微光。\",\"ImageURL\":\"https://everphoto-media.jianying.com/origin/7639982443885298201?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=61af081a9b2a73c3a6f43f76b91c29cfd790fbb2&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0pVfYhPZTvA9a2cLe9RS2kMs38kR0bWWW8A7Ei12W-zrUA1sZTx_GODpM5FGUWNIM\",\"AssetID\":\"7639982443885298201\",\"Episodes\":[\"2\"],\"AppearanceName\":\"城市公园步道_0\"}],\"ExpectRenderImageCount\":1,\"ActualRenderImageCount\":1},{\"SceneID\":\"1194108981004\",\"Name\":\"街角奶茶店\",\"AppearanceDetails\":[{\"AppearanceID\":\"1193840467212\",\"Description\":\"视角位于奶茶店内，聚焦在靠窗的一个双人座位。夜晚，室内明亮的暖黄色灯光将空间烘托得十分温馨。一张小方桌靠着窗户，桌上摆放着饮品。记忆点：透过宽大的玻璃窗，可以看到外面街道的夜景，窗格上同时倒映着店内的温暖光晕。\",\"ImageURL\":\"https://everphoto-media.jianying.com/origin/7639982400664551961?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=4306bea6cd800a3b130205255be6bb846967b854&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X26fCdjMvLqQwBAXCTN2XfVF6gn7ruwGC2vLYm1EmtYg-zCN_6mkdgmJb7cfklaOyA\",\"AssetID\":\"7639982400664551961\",\"Episodes\":[\"1\"],\"AppearanceName\":\"街角奶茶店_0\"}],\"ExpectRenderImageCount\":1,\"ActualRenderImageCount\":1},{\"SceneID\":\"1193993438988\",\"Name\":\"公园许愿池\",\"AppearanceDetails\":[{\"AppearanceID\":\"1194314405900\",\"Description\":\"机位设置在许愿池旁的石板小径上，平视角度。画面中心是经典的圆形石砌许愿池，池水在夜色中倒映着微光。一盏复古造型的路灯在池边投下温暖的黄色光圈，照亮了一小片区域和波光粼粼的水面。背景是公园里模糊的树木轮廓，光线无法触及的远处是深邃的阴影。记忆点：池边唯一亮着的、投下暖黄光圈的复古路灯。\",\"ImageURL\":\"https://everphoto-media.jianying.com/origin/7639982399301386777?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=e2a280dd856d0908b62672af92a6843707721a4a&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X2exTdw7dpLqVGnWN-jkC74Li2ngzdbX3yaMj94JUvalAz5Bh7FZAKiZL5bSRh-Zqw\",\"AssetID\":\"7639982399301386777\",\"Episodes\":[\"3\"],\"AppearanceName\":\"公园许愿池_0\"}],\"ExpectRenderImageCount\":1,\"ActualRenderImageCount\":1}],\"image_count\":5}",
        "status": "done"
    },
    "message": "Success",
    "request_id": "20260515131437F7C71C34F53AEDF1169D",
    "status": 10000,
    "time_elapsed": "93.206299ms"
}
```


&nbsp;


<span id="zj09q5df"></span>
### resp_data 反序列化结果展示

<div data-tips="true" data-tips-type="default" data-tips-is-title="true">说明</div>



1. <div data-tips="true" data-tips-type="default">可遍历 character_detail（角色资源详细内容）中的每一组 ExpectRenderImageCount（预期渲染图数量）和 ActualRenderImageCount（实际成功渲染图数量），当存在任意 ExpectRenderImageCount 不等于 ActualRenderImageCount 时表示有角色资源图片生成失败；</div>


2. <div data-tips="true" data-tips-type="default">同上，可遍历 scene_detail（场景资源详细内容）中的每一组 ExpectRenderImageCount（预期渲染图数量）和 ActualRenderImageCount（实际成功渲染图数量），当存在任意 ExpectRenderImageCount 不等于 ActualRenderImageCount 时表示有场景资源图片生成失败；</div>


3. <div data-tips="true" data-tips-type="default">生成失败的图片不支持重新生成或上传外部图片；</div>


4. <div data-tips="true" data-tips-type="default">图片生成失败最常见原因为审核不通过，请检查剧本中是否有涉及敏感身份、职业角色或者不合规的人物特征设定；</div>



```JSON
{
    "thread_id": "ark_3572523320385040940",
    "assets_id": "ark_1194097890828",
    "status": "Success",
    "character_detail": [
        {
            "CharacterID": "C1",
            "CharacterName": "陈屿",
            "IsMainCharacter": true,
            "Introduction": "陈屿是一位深情且细心的都市青年，是许知夏的男友。他珍视与女友的感情，对两人相处的点滴细节记忆犹新，并精心策划了求婚。在关键时刻他会表现出紧张和犹豫，但最终能够鼓起勇气，用真诚坚定的态度表达爱意，成功向许知夏求婚，从男友转变为未婚夫。他的形象是当代浪漫关系中一个普通但真挚的男性代表。",
            "TagInfos": [
                {
                    "Name": "基础形象",
                    "Identity": [
                        "许知夏的男友",
                        "上班族"
                    ],
                    "Personality": "深情专一、细心体贴、有仪式感、关键时刻会紧张犹豫、内在坚定",
                    "Background": "生活在都市，与女友许知夏交往至少两年，两人有固定的约会地点（奶茶店）和充满回忆的场所（公园许愿池）。是一名上班族。",
                    "Gender": "男",
                    "AgeGroup": "青年",
                    "VoiceInfo": {
                        "Description": "男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中"
                    },
                    "AppearanceInfo": {
                        "Description": "一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。"
                    },
                    "IsCore": true
                }
            ],
            "AppearanceTree": {
                "NodeID": "346df3d0-b035-4057-9fd2-a519b9a8e4e0",
                "AssetID": "1193731783692",
                "Detail": {
                    "NodeID": "",
                    "Name": "陈屿",
                    "StageName": "基础形象",
                    "Label": "基础形象",
                    "FullName": "陈屿-基础形象-基础形象",
                    "IsRoot": true,
                    "Appearance": "一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。",
                    "VoiceInfo": {
                        "Description": "男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中"
                    },
                    "BodyImageID": "7639981941240136217",
                    "BustPortraitID": "7639981897310175769",
                    "RelatedEpisodeNum": [
                        "1",
                        "2",
                        "3"
                    ],
                    "BodyImageURL": "https://everphoto-media.jianying.com/origin/7639981941240136217?X-Everphoto-Expires=1784006045&X-Everphoto-Sum=ac518e0a01bb277d617f5a4d21f87e6a68b9e500&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0ogTxYJ5eFx3RTA8X5Xr62WtXCw0fDXoIP8WgHtnMOOJhGuGtSw7uaGfmYJxH1hfE",
                    "BustPortraitURL": "https://everphoto-media.jianying.com/origin/7639981897310175769?X-Everphoto-Expires=1784006045&X-Everphoto-Sum=7c5c79708961b2cb7b07083c26f473ef5cbc804a&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X2RyqEqW-LUS8MMuWoY8hicqAk8ZEtVJsHKFhdZHbapUbEaniKx32kQ2oEdGK4ahVU"
                }
            },
            "ExpectRenderImageCount": 1,
            "ActualRenderImageCount": 1
        },
        {
            "CharacterID": "C2",
            "CharacterName": "许知夏",
            "Alias": [
                "知夏"
            ],
            "Introduction": "许知夏是男主角陈屿的女友，后成为其未婚妻。她是一个情感细腻、善于观察且略带俏皮的年轻女性。她珍视与陈屿的共同回忆，记得两人第一次约会的奶茶口味，同时也能够直接地表达自己的疑惑和情感。在陈屿的求婚下，她真情流露，欣然应允，开启了人生的新篇章。",
            "TagInfos": [
                {
                    "Name": "基础形象",
                    "Identity": [
                        "陈屿的女友",
                        "陈屿的未婚妻"
                    ],
                    "Personality": "情感细腻、恋旧（记得初次约会的奶茶）、观察力敏锐（能察觉到陈屿的心事）、性格直率且带点俏皮（会直接询问，也会假装生气）。在关键时刻真情流露，毫不犹豫地表达爱意。",
                    "Background": "与陈屿交往至少两年，两人第一次约会的地点是在一家街角奶茶店，感情稳定并最终接受了陈屿的求婚。",
                    "Gender": "女",
                    "AgeGroup": "青年",
                    "VoiceInfo": {
                        "Description": "女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中"
                    },
                    "AppearanceInfo": {
                        "Description": "一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。"
                    },
                    "IsCore": true
                }
            ],
            "AppearanceTree": {
                "NodeID": "82c4b0bc-c489-4eb2-957d-0bbee63e8cbd",
                "AssetID": "1194318554124",
                "Detail": {
                    "NodeID": "",
                    "Name": "许知夏",
                    "StageName": "基础形象",
                    "Label": "基础形象",
                    "FullName": "许知夏-基础形象-基础形象",
                    "IsRoot": true,
                    "Appearance": "一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。",
                    "VoiceInfo": {
                        "Description": "女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中"
                    },
                    "BodyImageID": "7639981959057572377",
                    "BustPortraitID": "7639981959057539609",
                    "RelatedEpisodeNum": [
                        "1",
                        "2",
                        "3"
                    ],
                    "BodyImageURL": "https://everphoto-media.jianying.com/origin/7639981959057572377?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=5324486e26e39bc98e3f94bbb11e31f9c61906b9&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0PmApliUcle2A-Ns_4VCbbCJr1cObG-2SDxTTPkKsG_1znP8ScTru6sWxM3FymoSI",
                    "BustPortraitURL": "https://everphoto-media.jianying.com/origin/7639981959057539609?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=7557531965b51e0d47f66e87848f2dde207f01dc&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0ZWDmzBVMmBXOQYYzz0EPmxS_Cx4Tx3YQHuUoJM3Qsd3kNIgAzntxs4RXt7pmMqDo"
                }
            },
            "ExpectRenderImageCount": 1,
            "ActualRenderImageCount": 1
        }
    ],
    "scene_detail": [
        {
            "SceneID": "1193827913740",
            "Name": "城市公园步道",
            "AppearanceDetails": [
                {
                    "AppearanceID": "1194314335244",
                    "Description": "机位设置在公园步道的一侧，呈中景视角。夜晚，暖黄色的路灯沿着石板铺就的小径向前延伸，在地面投下柔和的光斑。步道两侧是茂盛的绿植和几株桂花树，枝叶在夜色中呈现深绿色轮廓。记忆点：在步道延伸方向的远处背景中，可以看到一座亮着灯的圆形许愿池，水面反射着微光。",
                    "ImageURL": "https://everphoto-media.jianying.com/origin/7639982443885298201?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=61af081a9b2a73c3a6f43f76b91c29cfd790fbb2&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X0pVfYhPZTvA9a2cLe9RS2kMs38kR0bWWW8A7Ei12W-zrUA1sZTx_GODpM5FGUWNIM",
                    "AssetID": "7639982443885298201",
                    "Episodes": [
                        "2"
                    ],
                    "AppearanceName": "城市公园步道_0"
                }
            ],
            "ExpectRenderImageCount": 1,
            "ActualRenderImageCount": 1
        },
        {
            "SceneID": "1194108981004",
            "Name": "街角奶茶店",
            "AppearanceDetails": [
                {
                    "AppearanceID": "1193840467212",
                    "Description": "视角位于奶茶店内，聚焦在靠窗的一个双人座位。夜晚，室内明亮的暖黄色灯光将空间烘托得十分温馨。一张小方桌靠着窗户，桌上摆放着饮品。记忆点：透过宽大的玻璃窗，可以看到外面街道的夜景，窗格上同时倒映着店内的温暖光晕。",
                    "ImageURL": "https://everphoto-media.jianying.com/origin/7639982400664551961?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=4306bea6cd800a3b130205255be6bb846967b854&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X26fCdjMvLqQwBAXCTN2XfVF6gn7ruwGC2vLYm1EmtYg-zCN_6mkdgmJb7cfklaOyA",
                    "AssetID": "7639982400664551961",
                    "Episodes": [
                        "1"
                    ],
                    "AppearanceName": "街角奶茶店_0"
                }
            ],
            "ExpectRenderImageCount": 1,
            "ActualRenderImageCount": 1
        },
        {
            "SceneID": "1193993438988",
            "Name": "公园许愿池",
            "AppearanceDetails": [
                {
                    "AppearanceID": "1194314405900",
                    "Description": "机位设置在许愿池旁的石板小径上，平视角度。画面中心是经典的圆形石砌许愿池，池水在夜色中倒映着微光。一盏复古造型的路灯在池边投下温暖的黄色光圈，照亮了一小片区域和波光粼粼的水面。背景是公园里模糊的树木轮廓，光线无法触及的远处是深邃的阴影。记忆点：池边唯一亮着的、投下暖黄光圈的复古路灯。",
                    "ImageURL": "https://everphoto-media.jianying.com/origin/7639982399301386777?X-Everphoto-Expires=1784006046&X-Everphoto-Sum=e2a280dd856d0908b62672af92a6843707721a4a&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACrks7ceE8izm_JatoBU-X2exTdw7dpLqVGnWN-jkC74Li2ngzdbX3yaMj94JUvalAz5Bh7FZAKiZL5bSRh-Zqw",
                    "AssetID": "7639982399301386777",
                    "Episodes": [
                        "3"
                    ],
                    "AppearanceName": "公园许愿池_0"
                }
            ],
            "ExpectRenderImageCount": 1,
            "ActualRenderImageCount": 1
        }
    ],
    "image_count": 5
}
```





<span id="FbWykccK"></span>
# 单集分镜视频生成

> 选用 Seedance 2.0 fast 720p 接口详细说明请阅读[「小云雀-短剧漫剧Agent-视频生成-Seedance 2.0 fast 720p-接口文档」](https://www.volcengine.com/docs/85621/2389853?lang=zh)

> 选用 Seedance 2.0 720p 接口详细说明请阅读[「](https://www.volcengine.com/docs/85621/2389854?lang=zh)[小云雀-短剧漫剧Agent-视频生成-Seedance 2.0 720p-接口文档](https://www.volcengine.com/docs/85621/2389854?lang=zh)[」](https://www.volcengine.com/docs/85621/2389854?lang=zh)


<span id="OKLaguLj"></span>
## 提交任务

<span id="rSq2Ur6r"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_video_generate_pro720p",
    // "req_key": "pippit_shortplay_cvtob_video_generate_fast720p", 如果您选用的是 Seedance 2.0 fast 720p，请使用此 req_key
    "assets_id": "ark_1194097890828",  // 剧本解析返回的assets_id
    "thread_id": "ark_3572523320385040940",  // 剧本解析返回的thread_id
    "run_id": "example_video_generate_123456",
    "episode_id": "1"  // 指定生成的剧集ID
}
```


<span id="1aAoT5Rx"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "task_id": "5203772319199535374"
    },
    "message": "Success",
    "request_id": "202605151329593A743D484219252E6743",
    "status": 10000,
    "time_elapsed": "73.76889ms"
}
```


<span id="cixWx2CW"></span>
## 查询任务

<span id="aINxc9j8"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_video_generate_pro720p",
    // "req_key": "pippit_shortplay_cvtob_video_generate_fast720p", 如果您选用的是 Seedance 2.0 fast 720p，请使用此 req_key
    "task_id": "5203772319199535374"
}
```


<span id="2N5fwFX3"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "aigc_meta_tagged": false,
        "resp_data": "{\"thread_id\":\"ark_3572523320385040940\",\"assets_id\":\"ark_1194097890828\",\"status\":\"Success\",\"storyboard_detail\":[{\"EpisodeID\":\"1\",\"EpisodeAssetID\":\"1194108855308\",\"VisualStyle\":\"真人写实, 电影风格, 冷色调,都市女频\",\"RoleList\":[{\"RoleID\":\"R1\",\"RoleName\":\"许知夏-基础形象-基础形象\",\"VisualAttributes\":\"一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。\",\"VocalAttributes\":\"女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中\",\"MaterialID\":\"7639981959057572377\"},{\"RoleID\":\"R2\",\"RoleName\":\"陈屿-基础形象-基础形象\",\"VisualAttributes\":\"一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。\",\"VocalAttributes\":\"男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中\",\"MaterialID\":\"7639981941240136217\"}],\"LocationList\":[{\"LocationID\":\"L1\",\"LocationName\":\"街角奶茶店_0\",\"Description\":\"视角位于奶茶店内，聚焦在靠窗的一个双人座位。夜晚，室内明亮的暖黄色灯光将空间烘托得十分温馨。一张小方桌靠着窗户，桌上摆放着饮品。记忆点：透过宽大的玻璃窗，可以看到外面街道的夜景，窗格上同时倒映着店内的温暖光晕。\",\"MaterialID\":\"7639982400664551961\"}],\"ScriptStatus\":3,\"ShotStatusMap\":{\"S1\":{\"RunID\":\"078e03b023f31ed82809a00122d304c4_stage32\",\"Status\":3},\"S2\":{\"RunID\":\"078e03b023f31ed82809a00122d304c4_stage32\",\"Status\":3}},\"Shots\":[{\"ShotID\":\"S1\",\"Description\":\"画面风格和类型: 真人写实, 电影风格, 冷色调,都市女频。\\n生成一个由以下2个分镜组成的视频。\\n本片段场景设定在: <location>L1</location>。\\n分镜1<duration-ms>5000</duration-ms>: 夜晚的街角奶茶店，温馨的暖黄灯光裹着甜甜的奶香味。镜头缓缓推近，<role>R2</role>独自坐在靠窗的老位置，他面部朝向窗外的街道，眼神却总不自觉地飘向门口，放在桌下的手无意识地反复摩挲着口袋里的丝绒戒指盒，显露出内心的紧张与期待。画面中所有角色全程不说话。\\n分镜2<duration-ms>4000</duration-ms>: 在街角奶茶店柔和的灯光下，<role>R1</role>带着俏皮的微笑走到桌边，她面部朝向正襟危坐的<role>R2</role>，视线落在他身上。听到声音的<role>R2</role>猛地回过神，抬头看向她，眼神中闪过一丝慌乱。<role>R1</role>开口说：“你今天怎么这么早？我还以为要等你十分钟呢。”\\n\",\"Status\":3,\"VideoURL\":\"https://everphoto-internal.bytedance.net/everphoto/internal/download/id/7639988183442915902?X-Everphoto-Sum=68a094fe2ac4ad647d8f6c8fb204dca4bf0acf1d&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACJEZgTGRmJe8JSeF5SWFvDUPcqXcS9BCeqL6fO_xNtsSXEdArnffQzbzoNK8fab_yKCMQ8m8Wi2QcsZbeUv0MJ3ymYko6MpW_ugwPBbQb9WBaqmpmmj6P5jnYoXalcyMA\",\"ContentLength\":\"982\",\"Duration\":9056,\"ModelName\":\"seedance_2.0\",\"LocationIDList\":[\"L1\"],\"Version\":2,\"Width\":1280,\"Height\":720,\"Format\":\"MP4\",\"Size\":3367237,\"VideoAssetID\":\"7639988183442915902\"},{\"ShotID\":\"S2\",\"Description\":\"画面风格和类型: 真人写实, 电影风格, 冷色调,都市女频。\\n生成一个由以下3个分镜组成的视频。\\n本片段场景设定在: <location>L1</location>。\\n分镜1<duration-ms>4000</duration-ms>: 延续上一镜的状态，在街角奶茶店里，<role>R1</role>在<role>R2</role>的对面落座。为了掩饰紧张，<role>R2</role>慌忙拿起桌上的冰美式抿了一口，他的视线短暂地落在杯子上，然后才迎向<role>R1</role>的目光，面部朝向她，有些结巴地解释道：“没、没有，今天下班早，就先过来了。”\\n分镜2<duration-ms>6000</duration-ms>: 特写镜头，一只店员的手将一杯芋泥奶冻奶茶轻轻放在<role>R1</role>面前，打断了正准备开口的<role>R2</role>。<role>R1</role>的视线从奶茶上移开，面部转向对面的<role>R2</role>，眼神温柔，嘴角带着怀念的笑意，她说：“还是你记得我最爱喝这个，我们第一次约会，你就是在这里请我喝的同款。”\\n分镜3<duration-ms>4000</duration-ms>: 在街角奶茶店温暖的灯光下，听到<role>R1</role>的话，<role>R2</role>的眼神瞬间变得无比柔软。他面部正对<role>R1</role>，视线专注地凝视着她，放在桌下的手再次攥紧了口袋里的丝绒戒指盒。<role>R2</role>轻声而坚定地说：“当然记得，怎么会忘。”\\n\",\"Status\":3,\"VideoURL\":\"https://everphoto-internal.bytedance.net/everphoto/internal/download/id/7639988204896125502?X-Everphoto-Sum=63a041885806af9941f80aed088fd4c832c94bb1&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACJEZgTGRmJe8JSeF5SWFvDpr-vZhvx4U1id6us-yYBiYLIM24jlljqmhHGP1-dNQpL-tmXVhLic8pEq1uPcyYUkFvf16nMRgcTFx7FrE4703oqZb0s1zn0bFLiUGsEbAA\",\"ContentLength\":\"1374\",\"Duration\":14071,\"ModelName\":\"seedance_2.0\",\"LocationIDList\":[\"L1\"],\"Version\":2,\"Width\":1280,\"Height\":720,\"Format\":\"MP4\",\"Size\":4171878,\"VideoAssetID\":\"7639988204896125502\"}]}],\"charge_count\":23}",
        "status": "done"
    },
    "message": "Success",
    "request_id": "202605151336594822F03A411BBDF32CA3",
    "status": 10000,
    "time_elapsed": "25.758457ms"
}
```


&nbsp;


<span id="50blNpmT"></span>
### resp_data 反序列化结果展示

<div data-tips="true" data-tips-type="default" data-tips-is-title="true">说明</div>



1. <div data-tips="true" data-tips-type="default">可通过遍历 ShotStatusMap（各分镜的状态映射）中的 Status（分镜状态），确认所有分镜是否都成功完成；<strong>若存在生成失败的分镜，将无法调用视频合成接口生成最终视频</strong>；</div>


2. <div data-tips="true" data-tips-type="default">当少数分镜生成失败时，可保存失败分镜的 Description（分镜描述）以及图片生成接口返回的图片资源，前往第三方工具重新生成失败的分镜视频；并下载其余生成成功的分镜视频，通过第三方工具进行视频拼接，合成最终视频。</div>



```JSON
{
    "thread_id": "ark_3572523320385040940",
    "assets_id": "ark_1194097890828",
    "status": "Success",
    "storyboard_detail": [
        {
            "EpisodeID": "1",
            "EpisodeAssetID": "1194108855308",
            "VisualStyle": "真人写实, 电影风格, 冷色调,都市女频",
            "RoleList": [
                {
                    "RoleID": "R1",
                    "RoleName": "许知夏-基础形象-基础形象",
                    "VisualAttributes": "一名25岁左右的亚洲女性，中等身高，体态匀称纤细。鹅蛋脸，面部线条柔和，留着一头及胸的深棕色长卷发，发卷自然松散，配以轻盈的空气刘海。眼型是圆润的杏眼，瞳色为纯黑色，眼神常态清澈温和，透露出善于观察的敏锐感。五官精致，唇线偏薄。上身穿着一件低饱和度的雾霾蓝色哑光针织开衫，剪裁宽松舒适，内搭一件象牙白的哑光真丝混纺吊带衫。下身搭配一条深灰色的哑光质感A字长裙，裙长及小腿。脚上穿着一双白色的哑光质感板鞋，款式简约干净。标志性特征是她左手无名指上佩戴着的一枚款式简约的铂金钻戒，这是她被求婚的信物。她的帆布手提袋上挂着一个奶茶杯形状的小巧钥匙扣，作为她恋旧性格的叙事性细节。常态体态自然放松，整体气质温和亲切，兼具情感的细腻与性格的直率。",
                    "VocalAttributes": "女声，青年音色，音调适中，音色质感温润偏软，声音清亮松弛，发音干净利落，气息平稳绵长，带轻微的气音，吐字清晰，语速适中",
                    "MaterialID": "7639981959057572377"
                },
                {
                    "RoleID": "R2",
                    "RoleName": "陈屿-基础形象-基础形象",
                    "VisualAttributes": "一名26岁亚洲男性，身高约180cm，身形挺拔匀称、有属于上班族的清瘦感。脸型是线条流畅的椭圆脸，面部轮廓清晰柔和。留着清爽利落的黑色短发，发顶有自然的纹理感。眼型是内双的杏眼，眼尾略微下垂，纯黑瞳色，眼神常态温和专注，自带一股沉静安稳的气质。眉形自然、眉峰平缓，鼻梁高挺，唇线分明。身着一件低饱和度海军蓝色的哑光休闲西装外套，剪裁修身，内搭一件干净的米白色哑光棉质圆领T恤。下身是炭灰色的哑光修身休闲长裤，裤线笔直。脚穿一双深棕色的哑光系带休闲皮鞋，款式简约。标志性特征是左手腕佩戴的一枚设计简约的银色钢带手表，表盘干净无过多装饰，呼应他细心体贴、有仪式感的性格。常态站姿笔挺，整体气质干净沉稳，是深情而可靠的都市青年形象。",
                    "VocalAttributes": "男声，青年音色，音调偏中，音色质感温润偏沉，声音扎实平稳，发音字正腔圆，气息平稳绵长，说话时带有轻微的胸腔共鸣，吐字清晰有力，语速适中",
                    "MaterialID": "7639981941240136217"
                }
            ],
            "LocationList": [
                {
                    "LocationID": "L1",
                    "LocationName": "街角奶茶店_0",
                    "Description": "视角位于奶茶店内，聚焦在靠窗的一个双人座位。夜晚，室内明亮的暖黄色灯光将空间烘托得十分温馨。一张小方桌靠着窗户，桌上摆放着饮品。记忆点：透过宽大的玻璃窗，可以看到外面街道的夜景，窗格上同时倒映着店内的温暖光晕。",
                    "MaterialID": "7639982400664551961"
                }
            ],
            "ScriptStatus": 3,
            "ShotStatusMap": {
                "S1": {
                    "RunID": "078e03b023f31ed82809a00122d304c4_stage32",
                    "Status": 3
                },
                "S2": {
                    "RunID": "078e03b023f31ed82809a00122d304c4_stage32",
                    "Status": 3
                }
            },
            "Shots": [
                {
                    "ShotID": "S1",
                    "Description": "画面风格和类型: 真人写实, 电影风格, 冷色调,都市女频。\n生成一个由以下2个分镜组成的视频。\n本片段场景设定在: <location>L1</location>。\n分镜1<duration-ms>5000</duration-ms>: 夜晚的街角奶茶店，温馨的暖黄灯光裹着甜甜的奶香味。镜头缓缓推近，<role>R2</role>独自坐在靠窗的老位置，他面部朝向窗外的街道，眼神却总不自觉地飘向门口，放在桌下的手无意识地反复摩挲着口袋里的丝绒戒指盒，显露出内心的紧张与期待。画面中所有角色全程不说话。\n分镜2<duration-ms>4000</duration-ms>: 在街角奶茶店柔和的灯光下，<role>R1</role>带着俏皮的微笑走到桌边，她面部朝向正襟危坐的<role>R2</role>，视线落在他身上。听到声音的<role>R2</role>猛地回过神，抬头看向她，眼神中闪过一丝慌乱。<role>R1</role>开口说：“你今天怎么这么早？我还以为要等你十分钟呢。”\n",
                    "Status": 3,
                    "VideoURL": "https://everphoto-internal.bytedance.net/everphoto/internal/download/id/7639988183442915902?X-Everphoto-Sum=68a094fe2ac4ad647d8f6c8fb204dca4bf0acf1d&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACJEZgTGRmJe8JSeF5SWFvDUPcqXcS9BCeqL6fO_xNtsSXEdArnffQzbzoNK8fab_yKCMQ8m8Wi2QcsZbeUv0MJ3ymYko6MpW_ugwPBbQb9WBaqmpmmj6P5jnYoXalcyMA",
                    "ContentLength": "982",
                    "Duration": 9056,
                    "ModelName": "seedance_2.0",
                    "LocationIDList": [
                        "L1"
                    ],
                    "Version": 2,
                    "Width": 1280,
                    "Height": 720,
                    "Format": "MP4",
                    "Size": 3367237,
                    "VideoAssetID": "7639988183442915902"
                },
                {
                    "ShotID": "S2",
                    "Description": "画面风格和类型: 真人写实, 电影风格, 冷色调,都市女频。\n生成一个由以下3个分镜组成的视频。\n本片段场景设定在: <location>L1</location>。\n分镜1<duration-ms>4000</duration-ms>: 延续上一镜的状态，在街角奶茶店里，<role>R1</role>在<role>R2</role>的对面落座。为了掩饰紧张，<role>R2</role>慌忙拿起桌上的冰美式抿了一口，他的视线短暂地落在杯子上，然后才迎向<role>R1</role>的目光，面部朝向她，有些结巴地解释道：“没、没有，今天下班早，就先过来了。”\n分镜2<duration-ms>6000</duration-ms>: 特写镜头，一只店员的手将一杯芋泥奶冻奶茶轻轻放在<role>R1</role>面前，打断了正准备开口的<role>R2</role>。<role>R1</role>的视线从奶茶上移开，面部转向对面的<role>R2</role>，眼神温柔，嘴角带着怀念的笑意，她说：“还是你记得我最爱喝这个，我们第一次约会，你就是在这里请我喝的同款。”\n分镜3<duration-ms>4000</duration-ms>: 在街角奶茶店温暖的灯光下，听到<role>R1</role>的话，<role>R2</role>的眼神瞬间变得无比柔软。他面部正对<role>R1</role>，视线专注地凝视着她，放在桌下的手再次攥紧了口袋里的丝绒戒指盒。<role>R2</role>轻声而坚定地说：“当然记得，怎么会忘。”\n",
                    "Status": 3,
                    "VideoURL": "https://everphoto-internal.bytedance.net/everphoto/internal/download/id/7639988204896125502?X-Everphoto-Sum=63a041885806af9941f80aed088fd4c832c94bb1&X-Everphoto-Token=AAAAAAAAAAAAAAAAAAAAACJEZgTGRmJe8JSeF5SWFvDpr-vZhvx4U1id6us-yYBiYLIM24jlljqmhHGP1-dNQpL-tmXVhLic8pEq1uPcyYUkFvf16nMRgcTFx7FrE4703oqZb0s1zn0bFLiUGsEbAA",
                    "ContentLength": "1374",
                    "Duration": 14071,
                    "ModelName": "seedance_2.0",
                    "LocationIDList": [
                        "L1"
                    ],
                    "Version": 2,
                    "Width": 1280,
                    "Height": 720,
                    "Format": "MP4",
                    "Size": 4171878,
                    "VideoAssetID": "7639988204896125502"
                }
            ]
        }
    ],
    "charge_count": 23
}
```





&nbsp;

<span id="F6aDhGvN"></span>
# 单集视频合成

> 选用 Seedance 2.0 fast 720p 接口详细说明请阅读[「小云雀-短剧漫剧Agent-视频合成-Seedance 2.0 fast 720p-接口文档」](https://www.volcengine.com/docs/85621/2407085?lang=zh)

> 选用 Seedance 2.0 720p 接口详细说明请阅读[「](https://www.volcengine.com/docs/85621/2424562?lang=zh)[小云雀-短剧漫剧Agent-视频合成-Seedance 2.0 720p-接口文档](https://www.volcengine.com/docs/85621/2424562?lang=zh)[」](https://www.volcengine.com/docs/85621/2424562?lang=zh)


<span id="9gd0rT2C"></span>
## 提交任务

<span id="ADonkBxX"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_video_compose_pro720p",
    // "req_key": "pippit_shortplay_cvtob_video_compose_fast720p", 如果您选用的是 Seedance 2.0 fast 720p，请使用此 req_key
    "assets_id": "ark_1194097890828",  // 剧本解析返回的assets_id
    "thread_id": "ark_3572523320385040940",  // 剧本解析返回的thread_id
    "episode_id": "1"  // 指定生成的剧集ID
}
```


<span id="Xfb0L0ca"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "task_id": "5192240750742870496"
    },
    "message": "Success",
    "request_id": "20260515135503EACED0F86D2330611F5A",
    "status": 10000,
    "time_elapsed": "54.912613ms"
}
```


<span id="8Qzb1mnR"></span>
## 查询任务

<span id="VpNEpnn1"></span>
### 输入参数

```JSON
{
    "req_key": "pippit_shortplay_cvtob_video_compose_pro720p",
    // "req_key": "pippit_shortplay_cvtob_video_compose_fast720p", 如果您选用的是 Seedance 2.0 fast 720p，请使用此 req_key
    "task_id": "5192240750742870496"
}
```


<span id="mwCROPlj"></span>
### 输出参数

```JSON
{
    "code": 10000,
    "data": {
        "aigc_meta_tagged": false,
        "resp_data": "{\"thread_id\":\"ark_3572523320385040940\",\"run_id\":\"53e0140a516aacb8f2deba80d4d74416_stage41\",\"assets_id\":\"ark_1194097890828\",\"status\":\"Success\",\"storyboard_asset_id\":\"1194110367756\",\"final_video_url\":\"https://v11-default.365yg.com/62b71f3efe36ec824bddb05c5ef58695/6af4036c/video/n/everphoto-jianying-assets/52fa043ab19d4e7bb6b717108761fdae/?a=8700&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&br=6184&bt=6184&cs=0&ds=3&ft=Oi.pi77JWH6BM3-wbJr0PD1IN&mime_type=video_mp4&qs=13&rc=M3Jzc2lrb25lOzczNDlmM0BpM3Jzc2lrb25lOzczNDlmM0BfMHIzcWcvXjBhLS1kNC9zYSNfMHIzcWcvXjBhLS1kNC9zcw%3D%3D&btag=80000e00010000&dy_q=1778824533&l=20260515135503EACED0F86D2330611F5A&download=true&filename=v02c76g10004d83bak2ljhtf6pup3ob0.mp4\",\"final_video_cover_url\":\"https://p26-sign.douyinpic.com/everphoto-jianying-assets/oAfVr6VGTVjZGxewQstAQbYsYGZHBqMCgBBGIP~tplv-noop.image?dy_q=1778824533&l=20260515135503EACED0F86D2330611F5A&x-expires=1794376556&x-signature=lbKxO%2B8jFjsCrrZXlZk39Gcx214%3D\"}",
        "status": "done"
    },
    "message": "Success",
    "request_id": "20260515135742DEF79714753AD030ACEB",
    "status": 10000,
    "time_elapsed": "10.0512ms"
}
```


&nbsp;


<span id="yibDnZln"></span>
### resp_data 反序列化结果展示

```JSON
{
    "thread_id": "ark_3572523320385040940",
    "run_id": "53e0140a516aacb8f2deba80d4d74416_stage41",
    "assets_id": "ark_1194097890828",
    "status": "Success",
    "storyboard_asset_id": "1194110367756",
    "final_video_url": "https://v11-default.365yg.com/62b71f3efe36ec824bddb05c5ef58695/6af4036c/video/n/everphoto-jianying-assets/52fa043ab19d4e7bb6b717108761fdae/?a=8700&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&br=6184&bt=6184&cs=0&ds=3&ft=Oi.pi77JWH6BM3-wbJr0PD1IN&mime_type=video_mp4&qs=13&rc=M3Jzc2lrb25lOzczNDlmM0BpM3Jzc2lrb25lOzczNDlmM0BfMHIzcWcvXjBhLS1kNC9zYSNfMHIzcWcvXjBhLS1kNC9zcw%3D%3D&btag=80000e00010000&dy_q=1778824533&l=20260515135503EACED0F86D2330611F5A&download=true&filename=v02c76g10004d83bak2ljhtf6pup3ob0.mp4",
    "final_video_cover_url": "https://p26-sign.douyinpic.com/everphoto-jianying-assets/oAfVr6VGTVjZGxewQstAQbYsYGZHBqMCgBBGIP~tplv-noop.image?dy_q=1778824533&l=20260515135503EACED0F86D2330611F5A&x-expires=1794376556&x-signature=lbKxO%2B8jFjsCrrZXlZk39Gcx214%3D"
}
```





<span id="u2Y9yerT"></span>
# 输出视频展示


|剧集ID |剧集封面 |剧集视频 |
|---|---|---|
|1 |<span>![图片](https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_e332ed2c287da4f438f70d10cfd7c6b0.png) </span> |<video src="https://portal.volccdn.com/obj/volcfe/cloud-universal-doc/upload_476e0228b99678792d9913bcd382b304.mp4" controls></video><br><br><br> |


&nbsp;



