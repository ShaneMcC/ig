<#include "/header.ftl">
<div id="menu">
    <#list profiles as profile>
        <li><a href="/${profile}">${profile}</a></li>
    </#list>
</div>
<div id="app" class="container">
</div>
<#include "/footer.ftl">