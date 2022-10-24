var count=1;
$("#btn").click(function(){

  $("#container").append(addNewRow(count));
  count++;

});

function addNewRow(count){
  var newrow='<div class="row">'+
    '<div class="col-md-4">'+
        '<div class="form-group label-floating">'+
            '<label class="control-label">Act '+count+'</label>'+
            '<input type="text" class="form-control" v-model="act" >'+
        '</div>'+
    '</div>'+
    '<div class="col-md-4">'+
        '<div class="form-group label-floating">'+
            '<label class="control-label">Section '+count+'</label>'+
            '<input type="text" class="form-control" v-model="section">'+
        '</div>'+
    '</div>'+
'</div>';
  return newrow;
}