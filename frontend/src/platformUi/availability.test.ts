import {describe,it,expect} from 'vitest'
import {unconnectedPages,pageAvailability} from '../services/platform/availability'
import {navigation,templateNavigation,flattenNavigation} from '../router/navigation/navigation'
describe('Prevent mock screens from impersonating platform integrations',()=>{
 it('removes the retired report check entry from both navigation sources',()=>{for(const groups of [navigation,templateNavigation])expect(flattenNavigation(groups.flatMap(g=>g.children)).some(item=>item.to==='/reports/check')).toBe(false)});
 it('blocks every audited placeholder route with an explicit pending reason',()=>{expect(unconnectedPages.size).toBe(25);for(const [path,reason]of unconnectedPages){expect(pageAvailability(path)).toEqual({status:'pending',reason});expect(reason).not.toMatch(/已取消/)}});
 it('retains real workflows and distinguishes removed from pending',()=>{expect(pageAvailability('/inspection/entrust/registration').status).toBe('available');expect(pageAvailability('/reports/check').status).toBe('removed')});
});
