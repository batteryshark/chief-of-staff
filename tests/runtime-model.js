export default {id:'runway-test-model',async setup(ctx){
  await ctx.provider.transform(editor=>{
    const template=editor.list().flatMap(p=>[...p.models.values()])[0];
    if(!template)throw new Error('Model template missing');
    editor.add({info:{id:'runway-test',name:'Runway fixture',activation:'enabled',package:'@opencode/ai/providers/openai/chat',settings:{apiKey:'fixture',baseURL:`http://127.0.0.1:${process.env.RUNWAY_MODEL_PORT}/v1`}},models:['primary','fallback'].map(id=>({...template,id,modelID:id,providerID:'runway-test',package:'@opencode/ai/providers/openai/chat',status:'active',settings:{},capabilities:{tools:true,input:['text'],output:['text']},enabled:true,variants:[],cost:[],limit:{context:100000,output:10000}}))});
  });
}};
