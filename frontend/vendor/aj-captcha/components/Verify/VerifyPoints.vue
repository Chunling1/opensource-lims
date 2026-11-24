<template>
    <div style="position: relative"
        >
        <div class="verify-img-out">
            <div class="verify-img-panel rounded border bg-light overflow-hidden" :style="{'width': setSize.imgWidth,
                                                   'height': setSize.imgHeight,
                                                   'background-size' : setSize.imgWidth + ' '+ setSize.imgHeight,
                                                   'margin-bottom': vSpace + 'px'}"
                                                    >
                <button type="button" class="verify-refresh btn btn-light btn-icon btn-sm position-absolute top-0 end-0 m-2" style="z-index:3" aria-label="刷新验证码" :disabled="loading || pending" @click="refresh" v-show="showRefresh">
                    <i class="ri-refresh-line fs-16" aria-hidden="true"></i>
                </button>
                <img v-if="pointBackImgBase" :src="'data:image/png;base64,'+pointBackImgBase" 
                ref="canvas"
                alt="文字点选图" role="button" tabindex="0" aria-label="文字点选图，方向键移动，回车确认" :aria-disabled="!bindingClick || loading || pending" @keydown="keyboard" @blur="keyboardActive = false" style="width:100%;height:100%;display:block"
                @click="bindingClick?canvasClick($event):undefined">

                <span v-if="keyboardActive" class="bg-body text-body border border-primary" aria-hidden="true" :style="{position:'absolute', left:(keyboardPoint.x-8)+'px', top:(keyboardPoint.y-8)+'px', width:'16px', height:'16px', lineHeight:'16px', textAlign:'center', pointerEvents:'none', zIndex:4}">+</span>
                <div v-for="(tempPoint, index) in tempPoints" :key="index" class="point-area bg-success text-white"
                     :style="{
                        'pointer-events':'none',
                        'z-index':9999,
                        width:'20px',
                        height:'20px',
                        'text-align':'center',
                        'line-height':'20px',
                        'border-radius': '50%',
                        position:'absolute',
                        top:parseInt(tempPoint.y-10) + 'px',
                        left:parseInt(tempPoint.x-10) + 'px'
                     }">
                    {{index + 1}}
                </div>
            </div>
        </div>
        <!-- 'height': this.barSize.height, -->
        <div class="verify-bar-area rounded border small" :class="feedback === 'success' ? 'verify-result-success text-success border-success' : feedback === 'error' ? 'verify-result-error text-danger border-danger' : 'bg-light text-muted'"
             :style="{'width': setSize.imgWidth,
                      'line-height':this.barSize.height}">
            <span class="verify-msg" role="status">{{text}}</span>
        </div>
    </div>
</template>
<script type="text/babel">
    /**
     * VerifyPoints
     * @description 点选
     * */
    import {resetSize, _code_chars, _code_color1, _code_color2} from './../utils/util'
    import {aesEncrypt} from "./../utils/ase"
    import {useCaptchaApi} from "./../api/index"
    import { computed, onMounted, reactive, ref,watch,nextTick,toRefs, watchEffect,getCurrentInstance,onBeforeUnmount} from 'vue';
    export default {
        name: 'VerifyPoints',
        props: {
            //弹出式pop，固定fixed
            mode: {
                type: String,
                default: 'fixed'
            },
            captchaType:{
                type:String,
            },
            //间隔
            vSpace: {
                type: Number,
                default: 5
            },
            imgSize: {
                type: Object,
                default() {
                    return {
                        width: '310px',
                        height: '155px'
                    }
                }
            },
            barSize: {
                type: Object,
                default() {
                    return {
                        width: '310px',
                        height: '40px'
                    }
                }
            }
        },
        setup(props,context){
            const { reqGet, reqCheck } = useCaptchaApi()
            let disposed = false, imageRevision = 0
            const feedback = ref('')
            const pending = ref(false), loading = ref(false), keyboardActive = ref(false)
            const keyboardPoint = reactive({ x: 155, y: 77 })
            const timers = new Set()
            function later(fn, ms) {
                const id = setTimeout(() => { timers.delete(id); if (!disposed) fn() }, ms)
                timers.add(id)
            }
            onBeforeUnmount(() => { disposed = true; imageRevision++; timers.forEach(clearTimeout) })
            const {mode,captchaType,vSpace,imgSize,barSize} = toRefs(props)
            const { proxy } = getCurrentInstance();
            let secretKey = ref(''),           //后端返回的ase加密秘钥
                checkNum = ref(3),             //默认需要点击的字数
                fontPos = reactive([]),            //选中的坐标信息
                checkPosArr = reactive([]),        //用户点击的坐标
                num = ref(1),                 //点击的记数
                pointBackImgBase = ref(''),    //后端获取到的背景图片
                poinTextList = reactive([]),        //后端返回的点击字体顺序
                backToken = ref(''),           //后端返回的token值
                setSize = reactive({
                    imgHeight: 0,
                    imgWidth: 0,
                    barHeight: 0,
                    barWidth: 0
                }),
                tempPoints = reactive([]),
                text = ref(''),
                barAreaColor = ref(undefined),
                barAreaBorderColor = ref(undefined),
                showRefresh = ref(true),
                bindingClick = ref(true)

                
               

                const init = ()=>{
                    //加载页面
                    fontPos.splice(0, fontPos.length)
                    checkPosArr.splice(0, checkPosArr.length)
                    num.value = 1
                    getPictrue();
                    nextTick(() => {
                        let {imgHeight,imgWidth,barHeight,barWidth} = resetSize(proxy)
                        setSize.imgHeight = imgHeight
                        setSize.imgWidth = imgWidth
                        setSize.barHeight = barHeight
                        setSize.barWidth = barWidth
                        proxy.$parent.$emit('ready', proxy)
                    })
                }
                 onMounted(()=>{
                    // 禁止拖拽
                    init()
                    proxy.$el.onselectstart = function () {
                        return false
                    }
                })
                const canvas = ref(null)
                const canvasClick = (e)=>{
                    if (disposed || pending.value || loading.value || !bindingClick.value || !backToken.value) return;
                    if (!e.keyboard) keyboardActive.value = false;
                    checkPosArr.push(getMousePos(canvas, e));
                    if (num.value == checkNum.value) {
                        pending.value = true;
                        bindingClick.value = false;
                        num.value = createPoint(getMousePos(canvas, e));
                        //按比例转换坐标值
                        let arr = pointTransfrom(checkPosArr,setSize)
                        checkPosArr.length = 0
                        checkPosArr.push(...arr);
                        //等创建坐标执行完
                        later(() => {
                            // var flag = this.comparePos(this.fontPos, this.checkPosArr);
                            //发送后端请求
                            var captchaVerification = secretKey.value? aesEncrypt(backToken.value+'---'+JSON.stringify(checkPosArr),secretKey.value):backToken.value+'---'+JSON.stringify(checkPosArr)
                            let data = {
                                captchaType:captchaType.value,
                                "pointJson":secretKey.value? aesEncrypt(JSON.stringify(checkPosArr),secretKey.value):JSON.stringify(checkPosArr),
                                "token":backToken.value
                            }
                            reqCheck(data).then(res=>{
                                pending.value = false;
                                if (disposed) return;
                                if (res.repCode == "0000") {
                                    barAreaColor.value = '#4cae4c'
                                    barAreaBorderColor.value = '#5cb85c'
                                    feedback.value = 'success'
                                    text.value = '验证成功'
                                    showRefresh.value = false
                                    bindingClick.value = false
                                    if (mode.value=='pop') {
                                        later(()=>{
                                            proxy.$parent.clickShow = false;
                                            refresh();
                                        },1500)
                                    }
                                    proxy.$parent.$emit('success', {captchaVerification})
                                }else{
                                    proxy.$parent.$emit('error', proxy)
                                    barAreaColor.value = '#d9534f'
                                    barAreaBorderColor.value = '#d9534f'
                                    feedback.value = 'error'
                                    text.value = '验证失败'
                                    later(() => {
                                        refresh();
                                    }, 700);
                                }
                            })
                        }, 400);
                    }
                    if (num.value < checkNum.value) {
                        num.value = createPoint(getMousePos(canvas, e));
                    }
                }
                 //获取坐标
                const getMousePos = function (obj, e) {
                    var x = e.offsetX 
                    var y = e.offsetY 
                    return {x, y}
                }
                //创建坐标点
                const createPoint = function (pos) {
                    tempPoints.push(Object.assign({}, pos))
                    return num.value+1;
                }
                const refresh = function () {
                    if (disposed || pending.value || loading.value) return;
                    timers.forEach(clearTimeout); timers.clear(); keyboardActive.value = false;
                    feedback.value = ''
                    tempPoints.splice(0, tempPoints.length)
                    barAreaColor.value = '#000'
                    barAreaBorderColor.value = '#ddd'
                    bindingClick.value = true
                    fontPos.splice(0, fontPos.length)
                    checkPosArr.splice(0, checkPosArr.length)
                    num.value = 1
                    getPictrue();
                    text.value = ''
                    showRefresh.value = true
                }

                // 请求背景图片和验证图片
                function getPictrue() {
                    const revision = ++imageRevision;
                    loading.value = true; bindingClick.value = false; backToken.value = '';
                    let data = {
                        captchaType:captchaType.value
                    }
                    reqGet(data).then(res=>{
                        if (disposed || revision !== imageRevision) return;
                        loading.value = false;
                        if (res.repCode == "0000") {
                            bindingClick.value = true;
                            pointBackImgBase.value = res.repData.originalImageBase64
                            backToken.value = res.repData.token
                            secretKey.value = res.repData.secretKey
                            poinTextList.value = res.repData.wordList
                            text.value = '请依次点击【' + poinTextList.value.join(",") + '】'
                        }else{
                            feedback.value = 'error';
                            text.value = res.repMsg;
                        }
                    })
                }
                //坐标转换函数
                const pointTransfrom = function(pointArr,imgSize){
                    var newPointArr = pointArr.map(p=>{
                        let x = Math.round(310 * p.x/parseInt(imgSize.imgWidth)) 
                        let y =Math.round(155 * p.y/parseInt(imgSize.imgHeight)) 
                        return {x,y}
                    })
                    return newPointArr
                }
                function keyboard(e) {
                    if (!bindingClick.value || pending.value || loading.value) return;
                    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' '].includes(e.key)) return;
                    e.preventDefault(); keyboardActive.value = true;
                    const step = e.shiftKey ? 10 : 2;
                    if (e.key === 'ArrowLeft') keyboardPoint.x -= step;
                    if (e.key === 'ArrowRight') keyboardPoint.x += step;
                    if (e.key === 'ArrowUp') keyboardPoint.y -= step;
                    if (e.key === 'ArrowDown') keyboardPoint.y += step;
                    keyboardPoint.x = Math.max(0, Math.min(parseInt(setSize.imgWidth), keyboardPoint.x));
                    keyboardPoint.y = Math.max(0, Math.min(parseInt(setSize.imgHeight), keyboardPoint.y));
                    if (e.key === 'Enter' || e.key === ' ') canvasClick({offsetX:keyboardPoint.x, offsetY:keyboardPoint.y, keyboard:true});
                }
                return {
                    feedback, pending, loading, keyboard, keyboardActive, keyboardPoint,
                    secretKey,
                    checkNum,
                    fontPos,
                    checkPosArr,
                    num,
                    pointBackImgBase,
                    poinTextList,
                    backToken,
                    setSize,
                    tempPoints,
                    text,
                    barAreaColor,
                    barAreaBorderColor,
                    showRefresh,
                    bindingClick,
                    init,
                    canvas,
                    canvasClick,
                    getMousePos,createPoint,refresh,getPictrue,pointTransfrom
                }
        },
    }
</script>
