// token-helper.cpp —— 把 Token 直接焊在二进制里(无额外配置文件)。
// 用法: token-helper get <NAME>   —— 打印 NAME 对应的 token(供护栏 hook 内部使用)
//        token-helper has <NAME>   —— 0/1 是否存在(非空)
// 安全: 编译产物 token-helper 设 root:root 700; 值不进入会话/transcript(由调用方 hook 保证)。
// 你把各 GH_TOKEN_n 的真值填进下面 TOKENS 数组，然后重新 g++ 编译即可。
#include <cstdio>
#include <cstring>
struct Token { const char* name; const char* value; };
// —— 手动填写区：把每把 Metadata 只读细粒度 token 填到对应 value，类型保留原名 ——
static const Token TOKENS[] = {
  {"GH_TOKEN_1", ""},   // e.g. "github_pat_xxxxxxx"  所有者1(MagirecoCN-Revival-Project)
  {"GH_TOKEN_2", ""},   // 所有者2(Madoka-Realms)
  {"GH_TOKEN_3", ""},   // 所有者3(CyberNova2333 个人)
  {"GH_TOKEN",   ""},   // 兜底(可选)
  {nullptr, nullptr}
};
// —— 填写区结束 ——
static const char* find(const char* name){
  for(int i=0; TOKENS[i].name; ++i)
    if(!strcmp(TOKENS[i].name,name)) return TOKENS[i].value;
  return nullptr;
}
int main(int argc,char** argv){
  if(argc<3 || (strcmp(argv[1],"get")&&strcmp(argv[1],"has"))){fprintf(stderr,"usage: token-helper get|has <NAME>\n");return 2;}
  const char* v=find(argv[2]);
  int ok=(v&&v[0]);
  if(strcmp(argv[1],"get")==0){ if(ok) printf("%s",v); }
  return ok?0:1;
}
