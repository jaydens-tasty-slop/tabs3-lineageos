/* Vulkan 1.0 compute round trips. Public Vulkan ABI and Android libc only.
 * Drop root before loading the GPU; never access user storage or permissions.
 */
#include <vulkan/vulkan_core.h>
#include "vulkan_compute_spirv.h"
extern unsigned int getuid(void), geteuid(void), getgid(void);
extern int setuid(unsigned int), setgid(unsigned int), setgroups(unsigned long,const unsigned int *);
extern int open(const char *,int,...), close(int), printf(const char *,...);
extern long read(int,void *,unsigned long);
extern void *calloc(unsigned long,unsigned long);
extern void free(void *);
extern char *strstr(const char *,const char *);
struct probe_timespec { long sec,nsec; };
extern int clock_gettime(int,struct probe_timespec *);

static long elapsed_ms(void) {
    struct probe_timespec time;
    if(clock_gettime(1,&time))return -1;
    return time.sec*1000+time.nsec/1000000;
}

int main(void) {
    if(getuid()==0 && (setgroups(0,0)||setgid(2000)||setuid(2000)))return 64;
    if(getuid()!=2000||geteuid()!=2000||getgid()!=2000)return 65;
    char status[8192]={0};int fd=open("/proc/self/status",0);
    if(fd<0)return 66;
    long length=read(fd,status,sizeof(status)-1);close(fd);
    if(length<=0 || !strstr(status,"CapPrm:\t0000000000000000") ||
       !strstr(status,"CapEff:\t0000000000000000") || !strstr(status,"CapAmb:\t0000000000000000"))return 67;
    const char *stage="instance";VkResult result=VK_SUCCESS;int passed=0;
    VkInstance instance=0;VkPhysicalDevice physical=0;VkDevice device=0;
    VkBuffer buffer=0;VkDeviceMemory memory=0;void *mapped=0;
    VkDescriptorSetLayout descriptorLayout=0;VkDescriptorPool descriptorPool=0;
    VkPipelineLayout pipelineLayout=0;VkShaderModule shader=0;VkPipeline pipeline=0;
    VkCommandPool pool=0;VkCommandBuffer command=0;VkFence fence=0;
    VkPhysicalDeviceProperties properties={0};uint32_t tested=0;
    long started=elapsed_ms();
#define CHECK(expression) do {stage=#expression;result=(expression);if(result!=VK_SUCCESS)goto done;}while(0)
    VkApplicationInfo application={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName="TabS3 generated compute probe",.apiVersion=VK_API_VERSION_1_0};
    VkInstanceCreateInfo instanceInfo={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&application};
    CHECK(vkCreateInstance(&instanceInfo,0,&instance));
    uint32_t count=0;CHECK(vkEnumeratePhysicalDevices(instance,&count,0));
    if(!count || count>8){stage="bounded physical device count";goto done;}
    VkPhysicalDevice devices[8];CHECK(vkEnumeratePhysicalDevices(instance,&count,devices));
    for(uint32_t index=0;index<count;index++){
        vkGetPhysicalDeviceProperties(devices[index],&properties);
        if(properties.vendorID==0x5143 && properties.deviceType==VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
                && strstr(properties.deviceName,"Adreno")){physical=devices[index];break;}
    }
    if(!physical){stage="Qualcomm hardware GPU required";goto done;}
    for(unsigned int i=0;properties.deviceName[i];i++)
        if(properties.deviceName[i]=='"'||properties.deviceName[i]=='\\'||(unsigned char)properties.deviceName[i]<32)
            properties.deviceName[i]='_';
    uint32_t queues=0,family=UINT32_MAX;vkGetPhysicalDeviceQueueFamilyProperties(physical,&queues,0);
    if(!queues || queues>128){stage="bounded queue count";goto done;}
    VkQueueFamilyProperties families[128];vkGetPhysicalDeviceQueueFamilyProperties(physical,&queues,families);
    for(uint32_t i=0;i<queues;i++)if(families[i].queueCount && (families[i].queueFlags&VK_QUEUE_COMPUTE_BIT)){family=i;break;}
    if(family==UINT32_MAX){stage="compute queue required";goto done;}
    float priority=1;VkDeviceQueueCreateInfo queueInfo={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
    VkDeviceCreateInfo deviceInfo={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&queueInfo};
    CHECK(vkCreateDevice(physical,&deviceInfo,0,&device));VkQueue queue=0;vkGetDeviceQueue(device,family,0,&queue);
    VkBufferCreateInfo bufferInfo={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=128*sizeof(uint32_t),
        .usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    CHECK(vkCreateBuffer(device,&bufferInfo,0,&buffer));
    VkMemoryRequirements requirements;vkGetBufferMemoryRequirements(device,buffer,&requirements);
    VkPhysicalDeviceMemoryProperties types;vkGetPhysicalDeviceMemoryProperties(physical,&types);uint32_t type=UINT32_MAX;
    for(uint32_t i=0;i<types.memoryTypeCount;i++)
        if((requirements.memoryTypeBits&(1u<<i)) &&
           (types.memoryTypes[i].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))
            ==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){type=i;break;}
    if(type==UINT32_MAX || requirements.size>16777216){stage="bounded coherent host memory required";goto done;}
    VkMemoryAllocateInfo allocation={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize=requirements.size,.memoryTypeIndex=type};
    CHECK(vkAllocateMemory(device,&allocation,0,&memory));CHECK(vkBindBufferMemory(device,buffer,memory,0));
    CHECK(vkMapMemory(device,memory,0,requirements.size,0,&mapped));
    VkDescriptorSetLayoutBinding binding={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo layoutInfo={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount=1,.pBindings=&binding};
    CHECK(vkCreateDescriptorSetLayout(device,&layoutInfo,0,&descriptorLayout));
    VkDescriptorPoolSize poolSize={.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1};
    VkDescriptorPoolCreateInfo descriptorPoolInfo={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets=1,.poolSizeCount=1,.pPoolSizes=&poolSize};
    CHECK(vkCreateDescriptorPool(device,&descriptorPoolInfo,0,&descriptorPool));
    VkDescriptorSetAllocateInfo setInfo={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool=descriptorPool,.descriptorSetCount=1,.pSetLayouts=&descriptorLayout};
    VkDescriptorSet descriptor=0;CHECK(vkAllocateDescriptorSets(device,&setInfo,&descriptor));
    VkDescriptorBufferInfo descriptorBuffer={.buffer=buffer,.offset=0,.range=128*sizeof(uint32_t)};
    VkWriteDescriptorSet write={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=descriptor,.dstBinding=0,
        .descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&descriptorBuffer};
    vkUpdateDescriptorSets(device,1,&write,0,0);
    VkPushConstantRange constants={.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,.offset=0,.size=sizeof(uint32_t)};
    VkPipelineLayoutCreateInfo pipelineLayoutInfo={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount=1,.pSetLayouts=&descriptorLayout,.pushConstantRangeCount=1,.pPushConstantRanges=&constants};
    CHECK(vkCreatePipelineLayout(device,&pipelineLayoutInfo,0,&pipelineLayout));
    VkShaderModuleCreateInfo shaderInfo={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize=sizeof(probe_spirv),.pCode=probe_spirv};
    CHECK(vkCreateShaderModule(device,&shaderInfo,0,&shader));
    VkComputePipelineCreateInfo pipelineInfo={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,
                .module=shader,.pName="main"},.layout=pipelineLayout};
    CHECK(vkCreateComputePipelines(device,0,1,&pipelineInfo,0,&pipeline));
    VkCommandPoolCreateInfo commandPoolInfo={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=family};
    CHECK(vkCreateCommandPool(device,&commandPoolInfo,0,&pool));
    VkCommandBufferAllocateInfo commandInfo={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    CHECK(vkAllocateCommandBuffers(device,&commandInfo,&command));
    VkFenceCreateInfo fenceInfo={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};CHECK(vkCreateFence(device,&fenceInfo,0,&fence));
    for(uint32_t round=0;round<64;round++){
        if(elapsed_ms()-started>30000){stage="compute exceeded 30 seconds";goto done;}
        CHECK(vkResetCommandBuffer(command,0));
        VkCommandBufferBeginInfo beginInfo={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
            .flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
        CHECK(vkBeginCommandBuffer(command,&beginInfo));vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);
        vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipelineLayout,0,1,&descriptor,0,0);
        vkCmdPushConstants(command,pipelineLayout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(round),&round);
        vkCmdDispatch(command,2,1,1);
        VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,
            .srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,0,0,0);
        CHECK(vkEndCommandBuffer(command));CHECK(vkResetFences(device,1,&fence));
        VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&command};
        CHECK(vkQueueSubmit(queue,1,&submit,fence));CHECK(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ULL));
        for(uint32_t i=0;i<128;i++){
            if(((volatile uint32_t *)mapped)[i]!=((i*17u)^(0xa5a50000u+round))){stage="GPU result mismatch";goto done;}
            tested++;
        }
    }
    passed=tested==8192;stage="complete";
done:
    if(device){
        vkDeviceWaitIdle(device);
        if(fence)vkDestroyFence(device,fence,0);if(pool)vkDestroyCommandPool(device,pool,0);
        if(pipeline)vkDestroyPipeline(device,pipeline,0);if(shader)vkDestroyShaderModule(device,shader,0);
        if(pipelineLayout)vkDestroyPipelineLayout(device,pipelineLayout,0);
        if(descriptorPool)vkDestroyDescriptorPool(device,descriptorPool,0);
        if(descriptorLayout)vkDestroyDescriptorSetLayout(device,descriptorLayout,0);
        if(mapped)vkUnmapMemory(device,memory);if(buffer)vkDestroyBuffer(device,buffer,0);
        if(memory)vkFreeMemory(device,memory,0);vkDestroyDevice(device,0);
    }
    if(instance)vkDestroyInstance(instance,0);
    printf("TAB_S3_NATIVE_REPORT {\"passed\":%s,\"uid\":%u,\"gid\":%u,\"process_capabilities_zero\":true,"
           "\"device\":\"%s\",\"vendor_id\":%u,\"device_id\":%u,\"api_version\":%u,\"driver_version\":%u,"
           "\"rounds\":%u,\"verified_values\":%u,\"elapsed_ms\":%ld,\"stage\":\"%s\",\"vk_result\":%d}\n",
           passed?"true":"false",getuid(),getgid(),properties.deviceName,properties.vendorID,properties.deviceID,
           properties.apiVersion,properties.driverVersion,tested/128,tested,elapsed_ms()-started,stage,result);
    return passed?0:1;
}
