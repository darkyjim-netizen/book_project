<template>
  <figure class="analysis-donut" :aria-label="summary">
    <div class="donut-visual">
      <svg viewBox="0 0 200 200" role="img" :aria-label="summary"><title>{{ title }}</title>
        <circle cx="100" cy="100" r="76" fill="none" stroke="#eee9f3" stroke-width="25" />
        <circle v-for="part in slices" :key="part.label" cx="100" cy="100" r="76" fill="none" :stroke="part.color" stroke-width="25" pathLength="100" :stroke-dasharray="`${part.percent} ${100 - part.percent}`" :stroke-dashoffset="-part.offset" transform="rotate(-90 100 100)"><title>{{ part.label }}: {{ format(part.value) }}{{ unit }} ({{ part.percent.toFixed(1) }}%)</title></circle>
      </svg>
      <div class="donut-center"><strong>{{ centerValue ?? format(total) }}</strong><span>{{ centerLabel || unit }}</span></div>
    </div>
    <figcaption><h4>{{ title }}</h4><ul><li v-for="part in slices" :key="part.label"><i :style="{background:part.color}"></i><span>{{ part.label }}</span><b>{{ format(part.value) }}{{ unit }} <small>{{ part.percent.toFixed(1) }}%</small></b></li></ul><p v-if="!total">표시할 데이터가 없습니다.</p></figcaption>
  </figure>
</template>
<script setup>
import { computed } from 'vue';
const props=defineProps({title:String,items:{type:Array,default:()=>[]},unit:{type:String,default:'명'},centerValue:[String,Number],centerLabel:String});
const palette=['#7952ad','#a28bc7','#d58e9d','#68a9a1','#d4ae69','#8eaccc'];
const format=value=>Number(value||0).toLocaleString('ko-KR');
const total=computed(()=>props.items.reduce((sum,item)=>sum+Math.max(0,Number(item.value)||0),0));
const slices=computed(()=>{let offset=0;return props.items.map((item,index)=>{const value=Math.max(0,Number(item.value)||0),percent=total.value?value/total.value*100:0;const part={...item,value,percent,offset,color:item.color||palette[index%palette.length]};offset+=percent;return part;});});
const summary=computed(()=>`${props.title}: ${slices.value.map(part=>`${part.label} ${format(part.value)}${props.unit}`).join(', ')}`);
</script>
<style scoped>
.analysis-donut{display:grid;grid-template-columns:minmax(180px,260px) minmax(0,1fr);align-items:center;gap:28px;margin:24px 0;padding:24px;border:1px solid #eee7f3;border-radius:14px;background:linear-gradient(135deg,#faf7fd,#fff)}.donut-visual{position:relative;width:100%;max-width:260px;margin:auto}.donut-visual svg{display:block;width:100%;height:auto}.donut-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none}.donut-center strong{font-size:30px;color:#51316e}.donut-center span{margin-top:4px;font-size:15px;color:#82738c}figcaption{min-width:0}h4{margin:0 0 16px;font-size:18px;color:#493754}ul{list-style:none;padding:0;margin:0}li{display:flex;align-items:center;gap:9px;padding:10px 0;font-size:16px;border-bottom:1px solid #eee7f3}li i{width:11px;height:11px;flex:none;border-radius:50%}li span{flex:1;overflow-wrap:anywhere}li b{white-space:nowrap;font-size:16px}li small{margin-left:6px;font-size:14px;font-weight:400;color:#85758f}@media(max-width:650px){.analysis-donut{grid-template-columns:1fr;padding:16px;gap:12px}.donut-visual{max-width:220px}li{flex-wrap:wrap}}
</style>
