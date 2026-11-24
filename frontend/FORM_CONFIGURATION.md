# 表单配置接入

委托、样品和批量修改现在通过类型化配置复用表单渲染。业务接口、权限、默认值、保存、上传和业务联动仍由原页面与专用控件负责。

## 结构

- `src/types/forms.ts`：`FormSchema<T>`、字段与绑定类型、条件和配置检查。
- `src/components/forms/SchemaForm.vue`：卡片分区、栅格、标签、基础字段和业务插槽。不创建 HTML form，不请求接口。
- `src/components/forms/FormControl.vue`：文本、日期、数字、文本域、下拉、布尔下拉和复选框。
- `src/components/forms/FormTabs.vue`：使用现有 Arrow Nav tabs 的受控页签导航，面板生命周期仍由页面管理。
- `src/views/commissions/forms/commissionSchema.ts`、`sampleSchema.ts`：当前两张表单的配置与业务绑定。

委托基础字段及批量修改白名单保留在 `src/types/commissions/commissionFields.ts`，前后端共同使用。不要让服务端导入 Vue 渲染组件或 UI 配置。

## 普通字段与嵌套绑定

配置顺序就是显示顺序，使用稳定 id，而不是标签文字作为判断依据。不要用数组下标、当前输入值或 JSON 内容作为组件 key。

```ts
import type { FormSchema } from '../../../types/forms'
interface Model { details: { name: string; amount: string }; enabled: boolean }
const schema: FormSchema<Model> = {
  sections: [{
    id: 'basic', title: '基本信息', fields: [
      {
        id: 'record-name', label: '名称', control: 'text',
        width: 'col-md-6', required: true, maxlength: 150,
        binding: {
          get: model => model.details.name,
          set: (model, value) => { model.details.name = value },
        },
      },
      {
        id: 'record-amount', label: '金额', control: 'number',
        width: 'col-md-6', min: 0, step: 'any',
        disabled: model => !model.enabled,
        binding: {
          get: model => model.details.amount,
          set: (model, value) => { model.details.amount = value },
        },
      },
    ],
  }],
}
```

普通输入和普通下拉的绑定值是字符串，包括日期和字符串金额。数字控件本身不自动改变存储类型。确实需要数字模型时使用业务适配器，样品数量使用 `numberInputValue` 保留原 `v-model.number` 行为，包括清空时的空字符串。`boolean-select` 和 `checkbox` 的绑定值是布尔值，不能绑定到字符串属性。

`visible`、`disabled`、`readonly` 支持布尔值或纯条件函数。条件计算不应发请求、写模型或设置默认值。未显示/禁用字段不会被公共组件清空。保存时是否忽略其值由原业务规则决定。

错误通过 `errors` 传入，默认用控件 id 索引，也可配置 `errorKey` 对应接口字段。`requiredMark: false` 可以保留必填校验但不显示星号。基础控件生成提示与错误的 aria 关联。

## 接入业务控件

```ts
{ id: 'record-company', label: '单位', control: 'custom', slot: 'company', width: 'col-md-6' }
```

```vue
<SchemaForm :schema="schema" :model="model" :readonly="readonly" :errors="errors">
  <template #company="{ field, readonly, disabled }">
    <CompanyPicker :id="field.id" v-model="model.company" :readonly="readonly" :disabled="disabled" />
  </template>
</SchemaForm>
```

公共层已提供标签，专用控件应使用 `field.id`，不要再次生成同名标签或第二个输入框。专用控件需要自带复合标签时，字段配置 `ownLabel: true`；仅需要替换标签时使用 `labelSlot`。整个分区可使用 `slot`，此时其 `fields` 必须为空。

自定义组件继续处理自身异步状态、校验、取消/确认及错误重试。通过原页面的 `pending` 事件阻止未完成输入法编辑、解析或上传时保存；不引入统一自动提交草稿流程。检测地点即时更新，无需按回车提交。

检测依据/评定标准继续只允许选择列表中的内容并编辑分隔符；委托单位和生产单位继续允许直接编辑。公共渲染器不解析这些业务内容。

开发环境检查分区/字段重复 id、丢失的业务插槽和一个分区同时配置两种渲染方式。自定义控件内部的辅助控件也应使用唯一 id。

## 委托、样品与批量修改

委托表单和样品委托信息复用基础配置，但绑定不同模型。新建样品的单向复制仍由页面完成，配置不会持续同步原委托。

批量修改通过 `before-field` 插槽放置勾选框，通过配置禁用未勾选字段，提交仍从共享白名单生成 changes。不能从控件是否可见推导权限或允许修改的字段。

新增默认值仍在业务初始化时写入。委托日期取服务器日期；样品可编辑日期取客户端日期。重绘、切换页签和配置重新计算均不得重新写默认值。

## 验证

- `tests/unit/forms.test.ts` 检查配置、渲染、绑定类型、字段变体及数值保真。
- 相关 registration 浏览器测试覆盖保存、只读、单向复制、批量修改、专用控件和响应式布局。
- 每次变更运行适用测试、`npm run typecheck`；迁移验收另运行构建和 `npm run check:styles`。

后续表单优先组合这些基础能力，只有出现实际重复需求时再增加公共配置，避免业务字段名分支进入公共渲染层。


## 样品查看模式

样品新增、编辑、查看共用 RegistrationRecordView 中的完整样品表单及 sampleSchema，不再维护摘要字段布局。查看通过 readonly 传递至基础和业务控件，保留检测设置、Arrow Nav 页签、各分区、子项目查看和附件下载；隐藏修改、选择、上传及保存操作。检测依据与评定标准在查看时使用已保存文本，不依赖当前标准目录重新解析。样品选项元数据接口允许有样品读取权限的用户访问，不授予写权限；失效的已保存下拉值仍在只读模式显示。
