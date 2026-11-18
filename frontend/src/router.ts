import { createRouter, createWebHashHistory } from 'vue-router'
import Detection from './Detection.vue'
import MyTasks from './MyTasks.vue'
import Worksheet from './Worksheet.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', name: 'tasks', component: MyTasks },
    { path: '/samples', name: 'samples', component: Detection },
    { path: '/reports', name: 'reports', component: Detection },
    { path: '/samples/:sid(\\d+)', name: 'sample', component: Worksheet },
    { path: '/samples/:sid(\\d+)/reports/:rid(\\d+)', name: 'report', component: Worksheet },
  ],
  scrollBehavior(_to, _from, saved) {
    return saved ?? { top: 0 }
  },
})
