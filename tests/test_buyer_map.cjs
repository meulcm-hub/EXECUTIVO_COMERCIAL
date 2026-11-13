const test=require('node:test'),assert=require('node:assert/strict');
const q=require('../lcm-buyer-map.js');
const point=(extra={})=>({project:'residencial jatoba',city:'Sete Lagoas',uf:'MG',lat:-19.46,lng:-44.24,count:8,precision:'city',...extra});
const data={schema_version:1,coverage:{min_group_size:5},cities:[point(),point({project:'outro empreendimento',count:6})],neighborhoods:[point({precision:'neighborhood',neighborhood:'Centro'})]};
test('seleção acompanha empreendimento, cidade e tipo de localização',()=>{
 assert.equal(q.pointsFor(data,'RESIDENCIAL JATOBÁ','cities').length,1);
 assert.equal(q.pointsFor(data,'','cities').length,2);
 assert.equal(q.pointsFor(data,'residencial jatoba','neighborhoods',{city:'sete lagoas',uf:'MG'}).length,1);
 assert.equal(q.pointsFor(data,'residencial jatoba','neighborhoods',{city:'goiania',uf:'GO'}).length,0);
});
test('mesmo ponto reúne quantidades por empreendimento sem deslocar coordenadas',()=>{
 const groups=q.groupLocations(data.cities);assert.equal(groups.length,1);
 assert.equal(groups[0].lat,-19.46);assert.equal(groups[0].projects.get('residencial jatoba'),8);
 assert.equal(groups[0].projects.get('outro empreendimento'),6);
});
test('coordenadas inválidas ou grupos abaixo de cinco não chegam ao mapa',()=>{
 for(const bad of [point({count:4}),point({count:5.5}),point({lat:90}),point({lng:NaN}),point({uf:''}),point({precision:'neighborhood'})])assert.equal(q.validSource({...data,cities:[bad]}),false);
 assert.equal(q.validSource({...data,coverage:{min_group_size:1}}),false);
 assert.equal(q.validSource({...data,neighborhoods:[point({precision:'neighborhood'})]}),false);
});
