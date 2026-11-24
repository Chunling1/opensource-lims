<template>
    <div style="position: relative;">
        <div v-if="type === '2'" class="verify-img-out"
             :style="{height: (parseInt(setSize.imgHeight) + vSpace) + 'px'}"
            >
            <div class="verify-img-panel rounded border bg-light overflow-hidden" :style="{width: setSize.imgWidth,
                                                   height: setSize.imgHeight,}">
                <img v-if="backImgBase" :src="'data:image/png;base64,'+backImgBase" alt="" style="width:100%;height:100%;display:block">
                <div class="verify-sub-block position-absolute top-0 pe-none"
                     :style="{width: parseFloat(setSize.imgWidth) * 47 / 310 + 'px', height: setSize.imgHeight, left: position * parseFloat(setSize.imgWidth) / 310 + 'px', transition: transitionLeft}">
                    <img v-if="blockBackImgBase" :src="'data:image/png;base64,'+blockBackImgBase" alt="" style="width:100%;height:100%;display:block;-webkit-user-drag:none;">
                </div>
                <button type="button" class="verify-refresh btn btn-light btn-icon btn-sm position-absolute top-0 end-0 m-2" aria-label="刷新验证码" :disabled="loading || pending" @click="refresh" v-show="showRefresh"><i class="ri-refresh-line fs-16" aria-hidden="true"></i>
                </button>
                <transition name="tips">
                    <span role="status" class="verify-tips small text-center fw-medium" v-if="tipWords" :class="passFlag ? 'verify-result-success text-success' : 'verify-result-error text-danger'">{{tipWords}}</span>
                </transition>
            </div>
        </div>
        <!-- 公共部分 -->
        <div class="verify-bar-area rounded border bg-light text-muted" :style="{width: setSize.imgWidth,
                                              height: barSize.height,
                                              'line-height':barSize.height}">
            <span class="verify-msg" v-text="text"></span>
            <div class="verify-left-bar rounded border-0 top-0 start-0" :class="passFlag === true ? 'bg-success-subtle' : passFlag === false ? 'bg-danger-subtle' : 'bg-primary-subtle'"
                 :style="{width: (leftBarWidth!==undefined)?leftBarWidth: barSize.height, height: barSize.height, transition: transitionWidth}">
                <span class="verify-msg" v-text="finishText"></span>
                <div class="verify-move-block btn btn-icon rounded border-0 p-0" :class="passFlag === true ? 'btn-success' : passFlag === false ? 'btn-danger' : 'btn-soft-primary text-primary-emphasis'"
                     role="slider" tabindex="0" aria-label="安全验证" aria-valuemin="0" aria-valuemax="263" :aria-valuenow="Math.round(position)" :aria-disabled="loading || pending || isEnd || !backToken" @keydown="keyboard"
                     @touchstart="start"
                     @mousedown="start"
                     :style="{width: barSize.height, height: barSize.height, left: moveBlockLeft, transition: transitionLeft}">
                    <i class="fs-20" :class="passFlag === true ? 'ri-check-line' : passFlag === false ? 'ri-close-line' : 'ri-arrow-right-line'" aria-hidden="true"></i>
                </div>
            </div>
        </div>
    </div>
</template>
<script type="text/babel">
    /**
     * VerifySlide
     * @description 滑块
     * */
    import {aesEncrypt} from "./../utils/ase"
    import {resetSize} from './../utils/util'
    import {useCaptchaApi} from "./../api/index"
 import { computed, onMounted, reactive, ref,watch,nextTick,toRefs, watchEffect,getCurrentInstance,onBeforeUnmount} from 'vue';
    //  "captchaType":"blockPuzzle",
    export default {
        name: 'VerifySlide',
        props: {
            captchaType:{
                type:String,
            },
            type: {
                type: String,
                default: '1'
            },
            //弹出式pop，固定fixed
            mode: {
                type: String,
                default: 'fixed'
            },
            vSpace: {
                type: Number,
                default: 5
            },
            explain: {
                type: String,
                default: '向右滑动完成验证'
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
            blockSize: {
                type: Object,
                default() {
                    return {
                        width: '50px',
                        height: '50px'
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
            const {mode,captchaType,vSpace,imgSize,barSize,type,blockSize,explain} = toRefs(props)
            const { proxy } = getCurrentInstance();
            let secretKey = ref(''),           //后端返回的ase加密秘钥
                passFlag = ref(''),         //是否通过的标识
                backImgBase = ref(''),      //验证码背景图片
                blockBackImgBase = ref(''), //验证滑块的背景图片
                backToken = ref(''),        //后端返回的唯一token值
                startMoveTime = ref(''),    //移动开始的时间
                endMovetime = ref(''),      //移动结束的时间
                tipsBackColor = ref(''),    //提示词的背景颜色
                tipWords = ref(''),
                text = ref(''),
                finishText = ref(''),
                setSize = reactive({
                    imgHeight: 0,
                    imgWidth: 0,
                    barHeight: 0,
                    barWidth: 0
                }),
                top = ref(0),
                left = ref(0),
                position = ref(0),
                // 移动中样式
                moveBlockBackgroundColor = ref(undefined),
                leftBarBorderColor = ref('#ddd'),
                iconColor = ref(undefined),
                iconClass = ref('icon-right'),
                status = ref(false),	    //鼠标状态
                isEnd = ref(false) ,		//是够验证完成
                showRefresh = ref(true),
                transitionLeft = ref(''),
                transitionWidth = ref(''),
                startLeft = ref(0) 

                const barArea = computed(()=>{
                    return proxy.$el.querySelector('.verify-bar-area')
                })
                // A button and a puzzle have different widths. Map the same bounded
                // source-image coordinate to each one's available travel separately.
                const handleTravel = computed(() => Math.max(0, parseFloat(setSize.imgWidth || 0) - parseFloat(barSize.value.height)))
                const moveBlockLeft = computed(() => position.value / 263 * handleTravel.value + 'px')
                const leftBarWidth = computed(() => position.value / 263 * handleTravel.value + parseFloat(barSize.value.height) + 'px')
                let dragPosition = 0, dragging = false
                function setPosition(value) { position.value = Math.max(0, Math.min(263, Number.isFinite(value) ? value : 0)) }
                function cancelDrag() { dragging = false; status.value = false }
                let disposed = false, imageRevision = 0
                const pending = ref(false), loading = ref(false)
                const timers = new Set()
                function later(fn, ms) {
                    const id = setTimeout(() => { timers.delete(id); if (!disposed) fn() }, ms)
                    timers.add(id)
                }
                onBeforeUnmount(() => {
                    disposed = true; status.value = false; imageRevision++
                    timers.forEach(clearTimeout)
                    window.removeEventListener('touchmove', move)
                    window.removeEventListener('mousemove', move)
                    window.removeEventListener('touchend', end)
                    window.removeEventListener('mouseup', end)
                    window.removeEventListener('touchcancel', cancelDrag)
                })
                function init() {
                    text.value = explain.value
                    getPictrue();
                    nextTick(() => {
                        let {imgHeight,imgWidth,barHeight,barWidth} = resetSize(proxy)
                        setSize.imgHeight = imgHeight
                        setSize.imgWidth = imgWidth
                        setSize.barHeight = barHeight
                        setSize.barWidth = barWidth
                        proxy.$parent.$emit('ready', proxy)
                    })

                    window.addEventListener('touchmove', move, { passive: false });
                    window.addEventListener('mousemove', move);
                    window.addEventListener('touchend', end);
                    window.addEventListener('mouseup', end);
                    window.addEventListener('touchcancel', cancelDrag);
                }
                watch(type,()=>{
                    init()
                })
                onMounted(()=>{
                    // 禁止拖拽
                    init()
                    proxy.$el.onselectstart = function () {
                        return false
                    }
                })
                //鼠标按下
                function start(e) {
                    if (disposed || loading.value || pending.value || isEnd.value || !backToken.value || (!e.touches && e.button !== 0)) return
                    e = e || window.event
                    if (!e.touches) {  //兼容PC端 
                        var x = e.clientX;
                    } else {           //兼容移动端
                        var x = e.touches[0].clientX;
                    }

                    startLeft.value = x;
                    dragPosition = position.value; dragging = true;
                    transitionLeft.value = ''; transitionWidth.value = '';
                    startMoveTime.value = +new Date();    //开始滑动的时间
                    if (isEnd.value == false) {
                        text.value = ''
                        moveBlockBackgroundColor.value = '#337ab7'
                        leftBarBorderColor.value = '#337AB7'
                        iconColor.value = '#fff'
                        e.stopPropagation();
                        status.value = true;
                    }
                }
                //鼠标移动
                function move(e) {
                    e = e || window.event
                    if (dragging && status.value && isEnd.value == false && !pending.value) {
                        if (!e.touches) {  //兼容PC端 
                            var x = e.clientX;
                        } else {           //兼容移动端
                            var x = e.touches[0].clientX;
                        }
                        if (e.cancelable) e.preventDefault();
                        setPosition(dragPosition + (x - startLeft.value) * 263 / (handleTravel.value || 1));
                    }
                }

                //鼠标松开
                function end(event) {
                    if (event && !dragging) return;
                    dragging = false;
                    endMovetime.value = +new Date(); 
                    //判断是否重合
                    if (status.value && isEnd.value == false && !pending.value) {
                        var moveLeftDistance = position.value;
                        let data = {
                            captchaType:captchaType.value,
                            "pointJson":secretKey.value ? aesEncrypt(JSON.stringify({x:moveLeftDistance,y:5.0}),secretKey.value):JSON.stringify({x:moveLeftDistance,y:5.0}),
                            "token":backToken.value
                        }
                        pending.value = true;
                        reqCheck(data).then(res=>{
                            pending.value = false;
                            if (disposed) return;
                            if (res.repCode == "0000") {
                                moveBlockBackgroundColor.value = '#5cb85c'
                                leftBarBorderColor.value = '#5cb85c'
                                iconColor.value = '#fff'
                                iconClass.value = 'icon-check'
                                showRefresh.value = false
                                isEnd.value = true;   
                                if (mode.value=='pop') {
                                    later(()=>{
                                        proxy.$parent.clickShow = false;
                                        refresh();
                                    },1500)
                                }
                                passFlag.value = true
                                tipWords.value = `${((endMovetime.value-startMoveTime.value)/1000).toFixed(2)}s验证成功`
                                var captchaVerification = secretKey.value ? aesEncrypt(backToken.value+'---'+JSON.stringify({x:moveLeftDistance,y:5.0}),secretKey.value):backToken.value+'---'+JSON.stringify({x:moveLeftDistance,y:5.0})
                                later(()=>{
                                    tipWords.value = ""
                                    proxy.$parent.closeBox();
                                    proxy.$parent.$emit('success', {captchaVerification})
                                },1000)
                            }else{
                                moveBlockBackgroundColor.value = '#d9534f'
                                leftBarBorderColor.value = '#d9534f'
                                iconColor.value = '#fff'
                                iconClass.value = 'icon-close'
                                passFlag.value = false
                                isEnd.value = true;
                                later(function () {
                                    refresh();
                                }, 1000);
                                proxy.$parent.$emit('error',proxy)
                                tipWords.value = "验证失败"
                                later(()=>{
                                        tipWords.value = ""
                                },1000)
                            }
                        })
                        status.value = false;
                    }
                }

                const refresh = ()=>{
                    if (disposed || pending.value || loading.value) return;
                    timers.forEach(clearTimeout); timers.clear(); cancelDrag();
                    tipWords.value = ""; passFlag.value = "";
                    showRefresh.value = true
                    finishText.value = ''

                    transitionLeft.value = 'left .3s'
                    setPosition(0)

                    transitionWidth.value = 'width .3s'

                    leftBarBorderColor.value = '#ddd'
                    moveBlockBackgroundColor.value = '#fff'
                    iconColor.value = '#000'
                    iconClass.value = 'icon-right'
                    isEnd.value = false

                    getPictrue()
                    later(() => {
                        transitionWidth.value = ''
                        transitionLeft.value = ''
                        text.value = explain.value
                    }, 300)
                }

                // 请求背景图片和验证图片
                function getPictrue(){
                    const revision = ++imageRevision;
                    loading.value = true; backToken.value = "";
                    let data = {
                        captchaType:captchaType.value
                    }
                    reqGet(data).then(res=>{
                        if (disposed || revision !== imageRevision) return;
                        loading.value = false;
                        if (res.repCode == "0000") {
                            tipWords.value = "";
                            backImgBase.value = res.repData.originalImageBase64
                            blockBackImgBase.value = res.repData.jigsawImageBase64
                            backToken.value = res.repData.token
                            secretKey.value = res.repData.secretKey
                        }else{
                            tipWords.value = res.repMsg;
                        }
                    })
                }
                function keyboard(e) {
                    if (loading.value || pending.value || isEnd.value || !backToken.value) return;
                    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter', ' '].includes(e.key)) return;
                    e.preventDefault();
                    if (!status.value) { startMoveTime.value = +new Date(); status.value = true; }
                    transitionLeft.value = ''; transitionWidth.value = ''; text.value = '';
                    let value = position.value;
                    if (e.key === 'ArrowLeft') value--;
                    if (e.key === 'ArrowRight') value++;
                    if (e.key === 'Home') value = 0;
                    if (e.key === 'End') value = 263;
                    setPosition(value);
                    if (e.key === 'Enter' || e.key === ' ') end();
                }
                return {
                    keyboard, pending, loading, position,
                    secretKey,           //后端返回的ase加密秘钥
                    passFlag,         //是否通过的标识
                    backImgBase,      //验证码背景图片
                    blockBackImgBase, //验证滑块的背景图片
                    backToken,        //后端返回的唯一token值
                    startMoveTime,    //移动开始的时间
                    endMovetime,      //移动结束的时间
                    tipsBackColor,    //提示词的背景颜色
                    tipWords,
                    text,
                    finishText,
                    setSize,
                    top,
                    left,
                    moveBlockLeft,
                    leftBarWidth,
                    // 移动中样式
                    moveBlockBackgroundColor,
                    leftBarBorderColor,
                    iconColor,
                    iconClass,
                    status,	    //鼠标状态
                    isEnd,		//是够验证完成
                    showRefresh,
                    transitionLeft,
                    transitionWidth,
                    barArea,
                    refresh,
                    start
                }
        },
    }
</script>

