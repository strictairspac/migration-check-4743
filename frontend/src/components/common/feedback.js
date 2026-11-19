let current={message:'',error:false};
export function feedback(message,error=false){current={message,error};paint();}
export function paint(){const box=document.getElementById('feedback');if(!box)return;if(!current.message){box.hidden=true;return;}box.textContent=current.message;box.className=current.error?'feedback error':'feedback';box.hidden=false;}
export function clearFeedback(){current={message:'',error:false};paint();}
